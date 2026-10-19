from __future__ import annotations

from decimal import Decimal

from app.core.config import (
    STELLAR_ADMIN_SECRET,
    STELLAR_CONTRACT_ID,
    STELLAR_DECIMALS,
    STELLAR_NETWORK,
    STELLAR_RPC_URL,
    STELLAR_TOKEN_ID,
)


def amount_to_atomic(amount: Decimal | float, decimals: int = STELLAR_DECIMALS) -> int:
    value = Decimal(str(amount)) * (Decimal(10) ** decimals)
    if value != value.to_integral_value():
        raise ValueError("El monto no puede representarse con la precisión del token.")
    return int(value)


def ensure_confirmed_transaction(transaction_hash: str) -> None:
    if not STELLAR_RPC_URL:
        raise RuntimeError("Falta STELLAR_RPC_URL para verificar la transacción.")
    try:
        from stellar_sdk import SorobanServer
    except ImportError as exc:
        raise RuntimeError(
            "Instala stellar-sdk para verificar transacciones Stellar."
        ) from exc

    response = SorobanServer(STELLAR_RPC_URL).get_transaction(transaction_hash)
    status_value = getattr(response.status, "value", response.status)
    if status_value != "SUCCESS":
        raise ValueError(
            f"La transacción Stellar no está confirmada: {status_value}"
        )


def create_batch_on_chain(
    *,
    code: str,
    farm_id: int,
    title: str,
    description: str | None,
    category: str,
    target_amount: Decimal | float,
    price_per_share: Decimal | float,
    estimated_roi_percentage: Decimal | float,
    duration_months: int,
    funding_start_timestamp: int,
    funding_end_timestamp: int,
    farmer_address: str,
) -> str:
    """Publica un lote en Stellar usando su `code` (uuid4) como identificador.

    El `code` es estable entre reinicios de la base de datos, a diferencia del id
    autoincremental, por lo que el lote nunca colisiona con uno creado previamente.
    """
    if not farmer_address:
        raise ValueError(
            "La dirección Stellar del farmer es obligatoria para crear el batch."
        )
    if not code:
        raise ValueError("El código del batch es obligatorio para publicarlo en Stellar.")

    missing = [
        name
        for name, value in (
            ("STELLAR_CONTRACT_ID", STELLAR_CONTRACT_ID),
            ("STELLAR_TOKEN_ID", STELLAR_TOKEN_ID),
            ("STELLAR_ADMIN_SECRET", STELLAR_ADMIN_SECRET),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Falta configuración Stellar para crear el batch: " + ", ".join(missing)
        )

    try:
        from stellar_sdk import Keypair, Network, scval
        from stellar_sdk.contract import ContractClient
        from stellar_sdk.contract.exceptions import SimulationFailedError
    except ImportError as exc:
        raise RuntimeError(
            "Instala stellar-sdk para habilitar la publicación de batches en Stellar."
        ) from exc

    if STELLAR_NETWORK == "testnet":
        network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE
    elif STELLAR_NETWORK == "mainnet":
        network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE
    else:
        raise RuntimeError(f"Red Stellar no soportada: {STELLAR_NETWORK}")

    keypair = Keypair.from_secret(STELLAR_ADMIN_SECRET)
    client = ContractClient(
        contract_id=STELLAR_CONTRACT_ID,
        rpc_url=STELLAR_RPC_URL,
        network_passphrase=network_passphrase,
    )
    try:
        transaction = client.invoke(
            "create_batch",
            parameters=[
                scval.to_string(code),
                scval.to_uint64(farm_id),
                scval.to_string(title),
                scval.to_string(description or ""),
                scval.to_symbol(category),
                scval.to_address(farmer_address),
                scval.to_int128(amount_to_atomic(target_amount)),
                scval.to_int128(amount_to_atomic(price_per_share)),
                scval.to_int128(int(Decimal(str(estimated_roi_percentage)) * 100)),
                scval.to_uint32(duration_months),
                scval.to_uint64(funding_start_timestamp),
                scval.to_uint64(funding_end_timestamp),
            ],
            source=keypair.public_key,
            signer=keypair,
        )
    except SimulationFailedError as exc:
        raise RuntimeError(
            "El contrato rechazó los datos del batch durante la simulación. "
            "Verifica que el contrato desplegado esté actualizado y que los "
            "valores cumplan sus reglas de validación."
        ) from exc
    transaction.sign_and_submit()
    if transaction.send_transaction_response is None:
        raise RuntimeError("Stellar no devolvió confirmación de la transacción.")
    return transaction.send_transaction_response.hash


def get_batch_from_chain(code: str) -> dict:
    """Consulta en Stellar el estado de un lote a partir de su `code` (uuid4).

    Es la contraparte de lectura de `create_batch_on_chain`: ambas operaciones usan
    el mismo identificador estable, por lo que el lote sigue siendo localizable
    aunque la base de datos se reinicie o migre.
    """
    if not code:
        raise ValueError("El código del batch es obligatorio para consultarlo en Stellar.")
    if not STELLAR_CONTRACT_ID:
        raise RuntimeError("Falta STELLAR_CONTRACT_ID para consultar el batch.")

    try:
        from stellar_sdk import Keypair, Network, scval
        from stellar_sdk.contract import ContractClient
        from stellar_sdk.contract.contract_client import NULL_ACCOUNT
    except ImportError as exc:
        raise RuntimeError(
            "Instala stellar-sdk para habilitar la consulta de batches en Stellar."
        ) from exc

    if STELLAR_NETWORK == "testnet":
        network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE
    elif STELLAR_NETWORK == "mainnet":
        network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE
    else:
        raise RuntimeError(f"Red Stellar no soportada: {STELLAR_NETWORK}")

    client = ContractClient(
        contract_id=STELLAR_CONTRACT_ID,
        rpc_url=STELLAR_RPC_URL,
        network_passphrase=network_passphrase,
    )
    # `get_batch` no requiere autorización, así que basta una cuenta válida como origen.
    source = (
        Keypair.from_secret(STELLAR_ADMIN_SECRET).public_key
        if STELLAR_ADMIN_SECRET
        else NULL_ACCOUNT
    )
    # `invoke` con simulación devuelve el valor de retorno sin enviar la transacción.
    transaction = client.invoke(
        "get_batch",
        parameters=[scval.to_string(code)],
        source=source,
    )
    result = scval.to_native(transaction.result)
    if not isinstance(result, dict):
        raise RuntimeError("Stellar devolvió un lote con un formato inesperado.")
    return result
