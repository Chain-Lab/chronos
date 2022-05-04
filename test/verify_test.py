import binascii
import time

import ecdsa


pub = "89cd9047140ab2fe45f25b141ff451a2182836bf3f3346cddfe129c703e902359f0f180c5646a547d932dbfcbf03d0aa21b181dc6c86e4b5dfa952c8d5e0457b"
prv = "9beb4bdbe87c931b0517877819384b79847c2918ba575fa495f907aed4d77d0a"

sk = ecdsa.SigningKey.from_string(binascii.a2b_hex(prv), curve=ecdsa.SECP256k1)
signature = sk.sign("test".encode())

st = time.time()
vk = ecdsa.VerifyingKey.from_string(binascii.a2b_hex(pub), curve=ecdsa.SECP256k1)
vk.verify(signature, "test".encode())

ed = time.time()

print(ed - st)