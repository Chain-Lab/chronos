
BLOCK_PREFIX = "block#"
TRANSACTION_PREFIX = "tx#"
UTXO_PREFIX = "utxo#"


def blockhash_to_db_key(blockhash: str) -> str:
    """
    Convert blockhash to database key
    """
    return BLOCK_PREFIX + blockhash
