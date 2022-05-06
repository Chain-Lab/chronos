from core.block_chain import BlockChain


def get_tx_data(height):
    bc = BlockChain()
    heights = []
    result = []

    for i in range(height):
        print(i)
        block = bc.get_block_by_height(i)
        heights.append(i)
        result.append(len(block.transactions))

    print("heights: ", heights)
    print("result:", result)


def get_timestamp(height):
    bc = BlockChain()
    heights = []
    result = []

    block = bc.get_block_by_height(0)
    timestamp = int(block.block_header.timestamp)

    for i in range(1, height, 1):
        block = bc.get_block_by_height(i)
        heights.append(i)
        result.append((int(block.block_header.timestamp) - timestamp) / 1000)
        timestamp = int(block.block_header.timestamp)

    print("heights: ", height)
    print("result:", result)
