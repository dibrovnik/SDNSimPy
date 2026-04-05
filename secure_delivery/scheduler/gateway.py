from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import simpy

from secure_delivery.config import ExperimentConfig
from secure_delivery.crypto.engine import CryptoEngine
from secure_delivery.crypto.replay import ReplayWindow
from secure_delivery.metrics.collector import MetricsCollector
from secure_delivery.models.enums import MESSAGE_CLASS_ORDER, MessageClass, QueueDiscipline
from secure_delivery.models.message import SecureMessage
from secure_delivery.models.policy import ClassPolicy
from secure_delivery.models.profile import SecurityProfile
from secure_delivery.policy.manager import PolicyManager


@dataclass
class TransmissionBatch:
    messages: List[SecureMessage]
    message_class: MessageClass
    class_policy: ClassPolicy
    profile: SecurityProfile
    full_size_bytes: int
    tx_time_s: float


class GatewayScheduler:
    def __init__(
        self,
        env: simpy.Environment,
        config: ExperimentConfig,
        policy_manager: PolicyManager,
        crypto_engine: CryptoEngine,
        metrics: MetricsCollector,
        randomizer: random.Random,
    ) -> None:
        self.env = env
        self.config = config
        self.duration_s = config.duration_s
        self.policy_manager = policy_manager
        self.crypto_engine = crypto_engine
        self.metrics = metrics
        self.randomizer = randomizer
        self.crypto_resource = simpy.PriorityResource(env, capacity=config.crypto_workers)
        self.channel_resource = simpy.Resource(env, capacity=1)
        self.queue_discipline = (
            QueueDiscipline.DRR
            if config.queue_discipline == QueueDiscipline.WEIGHTED_PRIORITY
            else config.queue_discipline
        )
        self.class_queues: Dict[MessageClass, simpy.Store] = {
            message_class: simpy.Store(env)
            for message_class in MESSAGE_CLASS_ORDER
        }
        self.queue_signal = env.event()
        self.replay_windows: Dict[Tuple[str, str], ReplayWindow] = {}
        self.drr_deficits: Dict[MessageClass, int] = {message_class: 0 for message_class in MESSAGE_CLASS_ORDER}
        self.drr_cursor = 0
        self.drr_base_quantum_bytes = 256
        env.process(self._dispatch_loop())

    def submit(self, message: SecureMessage) -> None:
        self.metrics.register_message(message)
        self.env.process(self._ingest(message))

    def _ingest(self, message: SecureMessage):
        if self.config.classification_delay_s > 0:
            yield self.env.timeout(self.config.classification_delay_s)
        message.classified_at = self.env.now
        message.mark_event("classified_at", self.env.now)
        message.component_times["classification_time_s"] += self.config.classification_delay_s

        class_policy, profile = self.policy_manager.resolve_message_policy(message)
        if message.deadline_s <= 0:
            message.deadline_s = class_policy.deadline_s

        if not self.policy_manager.authorize(message):
            self._drop_message(message, "unauthorized", "ingress")
            return

        if profile.drop_before_encrypt and self._queue_size() >= self.config.channel.buffer_size:
            self._drop_message(message, "drop_before_encrypt", "ingress")
            return

        with self.crypto_resource.request(priority=class_policy.priority) as request:
            yield request
            crypto_start = self.env.now
            if message.crypto_start_at is None:
                message.crypto_start_at = crypto_start
            message.mark_event("crypto_start_at", crypto_start)
            crypto_time = self.crypto_engine.compute_crypto_time(profile, message.payload_bytes)
            if crypto_time > 0:
                yield self.env.timeout(crypto_time)
            crypto_end = self.env.now
            self.metrics.record_resource_interval("crypto", crypto_start, crypto_end)
            if message.crypto_end_at is None:
                message.crypto_end_at = crypto_end
            message.mark_event("crypto_end_at", crypto_end)
            message.component_times["crypto_time_s"] += crypto_end - crypto_start

        message.full_size_bytes = self.crypto_engine.compute_full_size(profile, message.payload_bytes)
        yield self.env.process(self._enqueue_message(message, class_policy))

    def _enqueue_message(self, message: SecureMessage, class_policy: ClassPolicy):
        if self._queue_size() >= self.config.channel.buffer_size and class_policy.drop_allowed:
            self._drop_message(message, "buffer_overflow", "enqueue")
            return

        message.current_attempt_queue_enter_at = self.env.now
        message.current_attempt_no = message.retransmission_count + 1
        if message.queue_enter_at is None:
            message.queue_enter_at = self.env.now
        message.mark_event("queue_enter_at", self.env.now, attempt=message.current_attempt_no)
        yield self.class_queues[message.message_class].put(message)
        self._record_queue_lengths()
        self._notify_dispatcher()

    def _notify_dispatcher(self) -> None:
        if not self.queue_signal.triggered:
            self.queue_signal.succeed()

    def _dispatch_loop(self):
        while True:
            if self._queue_size() == 0:
                yield self.queue_signal
                self.queue_signal = self.env.event()
                continue

            batch = self._select_next_batch()
            if batch is None:
                yield self.env.timeout(0)
                continue

            with self.channel_resource.request() as request:
                yield request
                tx_start = self.env.now
                for message in batch.messages:
                    if message.current_attempt_queue_enter_at is not None:
                        message.component_times["queue_time_s"] += tx_start - message.current_attempt_queue_enter_at
                    if message.queue_leave_at is None:
                        message.queue_leave_at = tx_start
                    message.mark_event("queue_leave_at", tx_start, attempt=message.current_attempt_no)
                    if message.tx_start_at is None:
                        message.tx_start_at = tx_start
                    message.mark_event("tx_start_at", tx_start, attempt=message.current_attempt_no)

                yield self.env.timeout(batch.tx_time_s)
                tx_end = self.env.now
                self.metrics.record_resource_interval("channel", tx_start, tx_end)
                for message in batch.messages:
                    if message.tx_end_at is None:
                        message.tx_end_at = tx_end
                    message.mark_event("tx_end_at", tx_end, attempt=message.current_attempt_no)
                    message.component_times["tx_time_s"] += batch.tx_time_s
                self.env.process(self._complete_transmission(batch))

    def _complete_transmission(self, batch: TransmissionBatch):
        if self.randomizer.random() < self.config.channel.loss_probability:
            for message in batch.messages:
                message.mark_event("tx_lost_at", self.env.now, attempt=message.current_attempt_no)
                self._handle_retry_or_drop(message, batch.class_policy, "channel_loss")
            return

        receiver_time = self.env.now
        duplicate_detected = False
        for message in batch.messages:
            if batch.profile.anti_replay:
                replay_key = (message.src, message.message_class.value)
                replay_window = self.replay_windows.setdefault(
                    replay_key,
                    ReplayWindow(size=self.config.replay_window_size),
                )
                accepted = replay_window.accept(
                    sequence_no=message.sequence_no,
                    at_time=receiver_time,
                    source_id=message.src,
                    stream_id=message.message_class.value,
                )
                if not accepted:
                    duplicate_detected = True
                    message.metadata["duplicate_replay_rejected"] = True

            if message.delivered_at is None:
                message.delivered_at = receiver_time
            message.mark_event("delivered_at", receiver_time, attempt=message.current_attempt_no)

        if batch.profile.ack_required:
            ack_start = self.env.now
            for message in batch.messages:
                if message.ack_wait_start_at is None:
                    message.ack_wait_start_at = ack_start
                message.mark_event("ack_wait_start_at", ack_start, attempt=message.current_attempt_no)
            if self.config.ack.delay_s > 0:
                yield self.env.timeout(self.config.ack.delay_s)
            ack_end = self.env.now
            if self.randomizer.random() < self.config.ack.loss_probability:
                for message in batch.messages:
                    message.component_times["ack_time_s"] += ack_end - ack_start
                    self._handle_retry_or_drop(message, batch.class_policy, "ack_loss")
                return

            for message in batch.messages:
                if message.ack_received_at is None:
                    message.ack_received_at = ack_end
                message.mark_event("ack_received_at", ack_end, attempt=message.current_attempt_no)
                message.component_times["ack_time_s"] += ack_end - ack_start
                message.delivered = True
                message.evaluate_deadline()
                if duplicate_detected:
                    message.metadata["ack_after_duplicate"] = True
        else:
            for message in batch.messages:
                message.delivered = True
                message.evaluate_deadline()

    def _handle_retry_or_drop(self, message: SecureMessage, class_policy: ClassPolicy, reason: str) -> None:
        if message.delivered:
            return
        if message.retransmission_count < class_policy.max_retransmissions:
            message.retransmission_count += 1
            backoff = max(self.config.ack.delay_s, self.config.channel.propagation_delay_s / 2.0)
            self.env.process(self._retry_later(message, class_policy, backoff, reason))
            return
        self._drop_message(message, reason, "retry")

    def _retry_later(self, message: SecureMessage, class_policy: ClassPolicy, delay_s: float, reason: str):
        message.mark_event("retry_scheduled_at", self.env.now, reason=reason, attempt=message.current_attempt_no)
        if delay_s > 0:
            yield self.env.timeout(delay_s)
        yield self.env.process(self._enqueue_message(message, class_policy))

    def _drop_message(self, message: SecureMessage, reason: str, stage: str) -> None:
        message.dropped = True
        message.drop_reason = reason
        message.dropped_at = self.env.now
        message.mark_event("dropped_at", self.env.now, reason=reason, stage=stage)
        message.metadata["drop_stage"] = stage
        message.evaluate_deadline()

    def _record_queue_lengths(self) -> None:
        self.metrics.record_queue_lengths(
            at_time=self.env.now,
            queue_lengths={message_class.value: len(store.items) for message_class, store in self.class_queues.items()},
        )

    def _queue_size(self) -> int:
        return sum(len(store.items) for store in self.class_queues.values())

    def _select_next_batch(self) -> Optional[TransmissionBatch]:
        selected_class = self._select_message_class()
        if selected_class is None:
            return None
        store = self.class_queues[selected_class]
        if not store.items:
            return None

        first_message = store.items.pop(0)
        class_policy, profile = self.policy_manager.resolve_message_policy(first_message)
        messages = [first_message]
        total_payload = first_message.payload_bytes

        if (
            selected_class == MessageClass.TELEMETRY
            and class_policy.aggregation_enabled
            and profile.batching_allowed
            and self.config.aggregation.max_messages > 1
        ):
            while (
                len(messages) < self.config.aggregation.max_messages
                and store.items
                and (
                    self.config.aggregation.max_payload_bytes <= 0
                    or total_payload + store.items[0].payload_bytes <= self.config.aggregation.max_payload_bytes
                )
            ):
                next_message = store.items.pop(0)
                messages.append(next_message)
                total_payload += next_message.payload_bytes

        self._record_queue_lengths()

        members = len(messages)
        full_size_bytes = self.crypto_engine.compute_full_size(
            profile=profile,
            payload_bytes=total_payload + self.config.aggregation.member_overhead_bytes * max(0, members - 1),
            members=members,
        )
        tx_time_s = (8.0 * full_size_bytes) / self.config.channel.bandwidth_bps + self.config.channel.propagation_delay_s
        for message in messages:
            message.metadata["aggregation_size"] = members
            message.metadata["effective_tx_bytes"] = full_size_bytes / float(members)
        return TransmissionBatch(
            messages=messages,
            message_class=selected_class,
            class_policy=class_policy,
            profile=profile,
            full_size_bytes=full_size_bytes,
            tx_time_s=tx_time_s,
        )

    def _select_message_class(self) -> Optional[MessageClass]:
        non_empty_classes = [message_class for message_class in MESSAGE_CLASS_ORDER if self.class_queues[message_class].items]
        if not non_empty_classes:
            return None

        if self.queue_discipline == QueueDiscipline.FIFO:
            return min(
                non_empty_classes,
                key=lambda message_class: self.class_queues[message_class].items[0].current_attempt_queue_enter_at or 0.0,
            )

        if self.queue_discipline == QueueDiscipline.STRICT_PRIORITY:
            return min(
                non_empty_classes,
                key=lambda message_class: self.policy_manager.get_class_policy(message_class).priority,
            )

        return self._select_message_class_drr(non_empty_classes)

    def _select_message_class_drr(self, non_empty_classes: List[MessageClass]) -> Optional[MessageClass]:
        classes = MESSAGE_CLASS_ORDER
        for _ in range(len(classes) * 8):
            message_class = classes[self.drr_cursor]
            self.drr_cursor = (self.drr_cursor + 1) % len(classes)
            store = self.class_queues[message_class]
            if not store.items:
                self.drr_deficits[message_class] = 0
                continue

            class_policy = self.policy_manager.get_class_policy(message_class)
            self.drr_deficits[message_class] += class_policy.weight * self.drr_base_quantum_bytes
            head_message = store.items[0]
            message_size = head_message.full_size_bytes or head_message.payload_bytes
            if message_size <= self.drr_deficits[message_class]:
                self.drr_deficits[message_class] -= message_size
                return message_class

        return min(
            non_empty_classes,
            key=lambda message_class: self.policy_manager.get_class_policy(message_class).priority,
        )

    def export_replay_events(self) -> List[Dict[str, object]]:
        events: List[Dict[str, object]] = []
        for replay_window in self.replay_windows.values():
            events.extend(replay_window.export_events())
        return events
