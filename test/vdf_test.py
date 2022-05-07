import time

if __name__ == "__main__":
    seed = 0xcae5a662faeb778ca9d4ec87dc84bccfd2da5d80b00d245f427ad676b3d33b81238dcc0adc2abc8014c772e60dce9e21aa5c61f30aa0ed41845b99e36047395b

    p = 0xcae5a662faeb778ca9d4ec87dc84bccfd2da5d80b00d245f427ad676b3d33b81238dcc0adc2abc8014c772e60dce9e21aa5c61f30aa0ed41845b99e36047395b
    q = 0x1f8d3210bb58cd9cb37278e5fa0eee8884d9346cec3348691c8a47abbae16000194ac79169ca18d2343983396bdca7c7efbb09ddb4fe520fb3af7756012ea531
    l = 0xc4937bdb61b73c87349f60706d8558d

    n = p * q
    t = 1000000
    calculated_round = 1
    result = seed
    pi, r = 1, 1
    start_time = time.time()
    while calculated_round <= t:
        result = result * result % n

        b = 2 * r // l
        r = 2 * r % l
        pi = (pi * pi % n) * (seed ** b % n)
        calculated_round += 1
    end_time = time.time()

    print(pi)
    print(result)
    print("time cost:", float(end_time - start_time) * 1000.0, "ms")

    # r = number_theory.quick_pow(2, t, l)
    # h = number_theory.quick_pow(pi, l, n) * number_theory.quick_pow(seed, r, n) % n
    # print(h)
