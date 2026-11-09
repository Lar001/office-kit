"""纯标准库 AES-256-GCM（无 cryptography 依赖），仅用于本机读取加密凭据。"""

SBOX = None

def _init_sbox():
    global SBOX
    # 标准 AES S-box，由 GF(2^8) 逆元 + 仿射变换生成
    p = 1
    q = 1
    sbox = [0] * 256
    sbox[0] = 0x63
    while True:
        # p 乘 3
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
        # q 除以 3
        q ^= q << 1
        q ^= q << 2
        q ^= q << 4
        q &= 0xFF
        if q & 0x80:
            q ^= 0x09
        x = q ^ ((q << 1) | (q >> 7)) ^ ((q << 2) | (q >> 6)) ^ ((q << 3) | (q >> 5)) ^ ((q << 4) | (q >> 4))
        sbox[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    SBOX = sbox


_init_sbox()
INV_SBOX = [0] * 256
for _i, _v in enumerate(SBOX):
    INV_SBOX[_v] = _i

RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36,
        0x6C, 0xD8, 0xAB, 0x4D]


def _xtime(a):
    return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else (a << 1) & 0xFF


def _mul(a, b):
    r = 0
    for _ in range(8):
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r


class AES:
    def __init__(self, key):
        nk = len(key) // 4
        if nk not in (4, 6, 8):
            raise ValueError("bad key size")
        self.nr = nk + 6
        w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
        for i in range(nk, 4 * (self.nr + 1)):
            t = list(w[i - 1])
            if i % nk == 0:
                t = t[1:] + t[:1]
                t = [SBOX[b] for b in t]
                t[0] ^= RCON[i // nk - 1]
            elif nk > 6 and i % nk == 4:
                t = [SBOX[b] for b in t]
            w.append([w[i - nk][j] ^ t[j] for j in range(4)])
        self.rk = w

    def _add_round_key(self, s, rnd):
        for c in range(4):
            for r in range(4):
                s[r][c] ^= self.rk[rnd * 4 + c][r]

    def encrypt_block(self, block):
        s = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
        self._add_round_key(s, 0)
        for rnd in range(1, self.nr + 1):
            for r in range(4):
                for c in range(4):
                    s[r][c] = SBOX[s[r][c]]
            s[1] = s[1][1:] + s[1][:1]
            s[2] = s[2][2:] + s[2][:2]
            s[3] = s[3][3:] + s[3][:3]
            if rnd != self.nr:
                for c in range(4):
                    a = [s[r][c] for r in range(4)]
                    s[0][c] = _mul(a[0], 2) ^ _mul(a[1], 3) ^ a[2] ^ a[3]
                    s[1][c] = a[0] ^ _mul(a[1], 2) ^ _mul(a[2], 3) ^ a[3]
                    s[2][c] = a[0] ^ a[1] ^ _mul(a[2], 2) ^ _mul(a[3], 3)
                    s[3][c] = _mul(a[0], 3) ^ a[1] ^ a[2] ^ _mul(a[3], 2)
            self._add_round_key(s, rnd)
        return bytes(s[r][c] for c in range(4) for r in range(4))


def _gmul(x, y):
    z = 0
    v = y
    for bit in range(128):
        if (x >> (127 - bit)) & 1:
            z ^= v
        if v & 1:
            v = (v >> 1) ^ 0xE1000000000000000000000000000000
        else:
            v >>= 1
    return z


def _ghash(h, data):
    x = 0
    for i in range(0, len(data), 16):
        blk = data[i:i + 16].ljust(16, b"\x00")
        x = _gmul(x ^ int.from_bytes(blk, "big"), h)
    return x.to_bytes(16, "big")


def _pad16(b):
    return b + b"\x00" * ((16 - len(b) % 16) % 16)


class GCM:
    def __init__(self, key, nonce):
        self.aes = AES(key)
        self.nonce = nonce
        self.h = int.from_bytes(self.aes.encrypt_block(b"\x00" * 16), "big")
        if len(nonce) == 12:
            j0 = nonce + b"\x00\x00\x00\x01"
        else:
            j0 = _ghash(self.h, _pad16(nonce) + b"\x00" * 8 + (len(nonce) * 8).to_bytes(8, "big"))
        self.j0 = j0

    def _ctr(self, data, start=2):
        out = bytearray()
        ctr = start
        for i in range(0, len(data), 16):
            ks = self.aes.encrypt_block(self.nonce + ctr.to_bytes(4, "big"))
            chunk = data[i:i + 16]
            out += bytes(a ^ b for a, b in zip(chunk, ks))
            ctr += 1
        return bytes(out)

    def _tag(self, aad, ct):
        s = _ghash(self.h, _pad16(aad) + _pad16(ct) +
                   (len(aad) * 8).to_bytes(8, "big") + (len(ct) * 8).to_bytes(8, "big"))
        ek = self.aes.encrypt_block(self.j0)
        return bytes(a ^ b for a, b in zip(s, ek))

    def encrypt(self, plaintext, aad=b""):
        ct = self._ctr(plaintext)
        return ct, self._tag(aad, ct)

    def decrypt(self, ct, tag, aad=b""):
        if self._tag(aad, ct) != tag:
            raise ValueError("tag mismatch")
        return self._ctr(ct)


if __name__ == "__main__":
    # FIPS-197 AES-256 已知答案测试
    k = bytes(range(32))
    pt = bytes.fromhex("00112233445566778899aabbccddeeff")
    ct = AES(k).encrypt_block(pt)
    assert ct.hex() == "8ea2b7ca516745bfeafc49904b496089", ct.hex()
    print("AES-256 KAT ok")
    # GCM 自洽测试
    g = GCM(bytes(range(32)), b"\x00" * 12)
    c, t = g.encrypt(b"hello world", b"aad")
    assert g.decrypt(c, t, b"aad") == b"hello world"
    print("GCM roundtrip ok")
