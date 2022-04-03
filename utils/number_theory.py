import os
import random
import sys

if sys.version_info >= (3,):  # pragma: no branch

    def entropy_to_bits(ent_256):
        """Convert a bytestring to string of 0's and 1's"""
        return bin(int.from_bytes(ent_256, "big"))[2:].zfill(len(ent_256) * 8)
else:
    def entropy_to_bits(ent_256):
        """Convert a bytestring to string of 0's and 1's"""
        return "".join(bin(ord(x))[2:].zfill(8) for x in ent_256)

if sys.version_info < (2, 7):  # pragma: no branch
    # Can't add a method to a built-in type so we are stuck with this
    def bit_length(x):
        return len(bin(x)) - 2
else:
    def bit_length(x):
        return x.bit_length() or 1
"""
Code from ecdsa: keys.py
"""

def quick_pow(a, b, p):
    """
    快速幂，计算a^b mod p
    """
    result = 1
    t = a
    while b:
        if b & 1:
            result = result * t % p
        b >>= 1
        t = t * t % p
    return result


def miller_rabin(random_number):
    """
    MillerRabin算法判断是否质数
    @param random_number: 待判断的数
    @return: 返回判断结果
    """
    if random_number == 1:
        return False

    if random_number == 2:
        return True

    if random_number % 2 == 0:
        return False

    m, k = random_number - 1, 0
    while m % 2 == 0:
        m, k = m // 2, k + 1
    a = random.randint(2, random_number - 1)
    x = quick_pow(a, m, random_number)
    if x == 1 or x == random_number - 1:
        return True
    while k > 1:
        x = quick_pow(x, 2, random_number)
        if x == 1:
            return False
        if x == random_number - 1:
            return True
        k = k - 1
    return False


def randrange(order, entropy=None):
    """Return a random integer k such that 1 <= k < order, uniformly
    distributed across that range. Worst case should be a mean of 2 loops at
    (2**k)+2.

    Note that this function is not declared to be forwards-compatible: we may
    change the behavior in future releases. The entropy= argument (which
    should get a callable that behaves like os.urandom) can be used to
    achieve stability within a given release (for repeatable unit tests), but
    should not be used as a long-term-compatible key generation algorithm.

    From python-ecdsa
    """
    assert order > 1
    if entropy is None:
        entropy = os.urandom
    upper_2 = bit_length(order - 2)
    upper_256 = upper_2 // 8 + 1
    while True:  # I don't think this needs a counter with bit-wise randrange
        ent_256 = entropy(upper_256)
        ent_2 = entropy_to_bits(ent_256)
        rand_num = int(ent_2[:upper_2], base=2) + 1
        if 0 < rand_num < order:
            return rand_num


def is_prime(random_number, _round=40):
    """
    调用Miller Rabin算法检查是否质数， 检查_round轮
    @param random_number: 选定的随机数
    @param _round: 检查的轮数
    @return:
    """
    for _ in range(_round):
        if miller_rabin(random_number) == False:
            return False
    return True


def get_prime(index):
    while True:
        random_number = random.getrandbits(index)
        while not is_prime(random_number):
            random_number = random_number + 1
        return random_number
