import threading
import time

from core.txmempool import TxMemPool


def thread_func():
    tx_mempool = TxMemPool()
    for i in range(100):
        time.sleep(2)
        txs = tx_mempool.package(i)
        print(txs)


if __name__ == "__main__":
    for _ in range(5):
        thread = threading.Thread(target=thread_func)
        thread.start()