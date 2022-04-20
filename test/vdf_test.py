from utils import number_theory

if __name__ == "__main__":
    seed = number_theory.get_prime(700)

    p = number_theory.get_prime(512)
    q = number_theory.get_prime(512)
    l = number_theory.get_prime(128)

    n = p * q
    t = 5000
    calculated_round = 1
    result = seed
    pi, r = 1, 1
    while calculated_round <= t:
        result = result * result % n

        b = 2 * r // l
        r = 2 * r % l
        pi = (pi * pi % n) * (seed ** b % n)
        calculated_round += 1

    print(pi)
    print(result)

    r = number_theory.quick_pow(2, t, l)
    h = number_theory.quick_pow(pi, l, n) * number_theory.quick_pow(seed, r, n) % n
    print(h)