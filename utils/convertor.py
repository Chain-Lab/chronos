
BLOCK_PREFIX = "block#"
TRANSACTION_PREFIX = "tx#"
UTXO_PREFIX = "utxo#"


def blockhash_to_db_key(blockhash: str) -> str:
    """
    Convert blockhash to database key
    """
    return BLOCK_PREFIX + blockhash


def tx_hash_to_db_key(tx_hash: str) -> str:
    """
    Convert tx hash to database key
    """
    return TRANSACTION_PREFIX + tx_hash


def utxo_hash_to_db_key(tx_hash: str, index: int) -> str:
    """
    Convert tx hash and index to db key
    """
    return UTXO_PREFIX + tx_hash + "#" + str(index)


def remove_utxo_db_prefix(utxo_db_key: str) -> str:
    return utxo_db_key.replace(UTXO_PREFIX, "")


def height_to_db_key(height: int) -> str:
    return BLOCK_PREFIX + str(height)


def addr_utxo_db_key(address: str) -> str:
    return UTXO_PREFIX + address