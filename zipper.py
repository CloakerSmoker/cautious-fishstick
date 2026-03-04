
import sys, zipfile, hashlib, zlib

target_file = sys.argv[1]

index = 0

with zipfile.ZipFile(target_file, 'r') as zip:
    for ze in zip.infolist():
        with zip.open(ze) as f:
            sha1 = hashlib.sha1()
            md5 = hashlib.md5()
            crc = 0

            while True:
                chunk = f.read(0x7FFFFFFF)

                if not chunk:
                    break

                sha1.update(chunk)
                md5.update(chunk)
                crc = zlib.crc32(chunk, crc)
            
            print(f'Entry {index}: {ze.filename}')
            print(f'MD5: {md5.hexdigest()}')
            print(f'SHA1: {sha1.hexdigest()}')
            print(f'CRC32: {crc:08x}')
            index += 1