from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any

try:
    from web3 import Web3
    from web3.exceptions import Web3Exception
except ImportError:
    Web3 = None
    Web3Exception = Exception

from secure_delivery.models.policy import PolicyVersion
from secure_delivery.models.profile import SecurityProfile

logger = logging.getLogger(__name__)


class IContractBackend(ABC):
    @abstractmethod
    def load(self) -> Dict[str, object]:
        raise NotImplementedError


class FilePolicyBackend(IContractBackend):
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def load(self) -> Dict[str, object]:
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)


class EvmPolicyBackend(IContractBackend):
    """
    Реальная интеграция с EVM-совместимым блокчейном для получения политик агентами.
    Включает устойчивость к ненадежной среде (обрывы сети, десинхронизация):
    - Экспоненциальный откат при ошибках (Exponential Backoff).
    - Кеширование последней валидной копии политики.
    """
    def __init__(self, rpc_url: str, contract_address: str, abi: list[Dict[str, Any]], local_cache_path: str = ".policy_cache.json", max_retries: int = 3, retry_delay: float = 2.0) -> None:
        if Web3 is None:
            raise ImportError("Библиотека web3 не установлена. Выполните 'pip install web3'.")
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.contract_address = self.w3.to_checksum_address(contract_address) if self.w3.is_address(contract_address) else contract_address
        self.abi = abi
        self.local_cache_path = Path(local_cache_path)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Если контракт корректный, инициализируем инстанс, иначе оставляем None (для тестов, где нет ноды)
        try:
            self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.abi)
        except Exception:
            self.contract = None

    def load(self) -> Dict[str, object]:
        if self.contract is None:
            return self._load_fallback()
            
        for attempt in range(self.max_retries):
            try:
                if not self.w3.is_connected():
                    raise ConnectionError("RPC провайдер Web3 недоступен.")
                
                # Запрашиваем ID последней версии политики
                latest_version_id = self.contract.functions.getLatestVersionId().call()
                # Забираем полезную нагрузку (может быть IPFS-хаш, URI или JSON-строка)
                policy_json_str = self.contract.functions.getPolicyPayload(latest_version_id).call()
                
                payload = json.loads(policy_json_str)
                
                # Успешно скачали — обновляем локальный кеш
                with self.local_cache_path.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                    
                return payload
                
            except Exception as e:
                logger.warning(f"EvmPolicyBackend: Ошибка получения политики (попытка {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt)) # Экспоненциальный бэкофф
                else:
                    logger.error("EvmPolicyBackend: Исчерпаны попытки загрузки смарт-контракта. Переход на кеш.")
                    
        return self._load_fallback()
        
    def _load_fallback(self) -> Dict[str, object]:
        if self.local_cache_path.exists():
            with self.local_cache_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        raise RuntimeError("Не удалось получить политику из блокчейна, и локальный кеш отсутствует.")


def load_policy_bundle(backend: IContractBackend) -> Dict[str, object]:
    payload = backend.load()
    profiles = {
        name: SecurityProfile.from_dict({"name": name, **dict(profile_payload)})
        for name, profile_payload in dict(payload.get("security_profiles", {})).items()
    }
    versions = {
        item["version_id"]: PolicyVersion.from_dict(dict(item))
        for item in payload.get("policy_versions", [])
    }
    return {
        "security_profiles": profiles,
        "policy_versions": versions,
        "metadata": dict(payload.get("metadata", {})),
    }
