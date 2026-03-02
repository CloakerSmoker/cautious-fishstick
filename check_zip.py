
import sys, os, hashlib, zipfile, pathlib
import xml.etree.ElementTree as ET
import tqdm

target_file = sys.argv[1]
dat_file = sys.argv[2]

target_file_name = os.path.basename(target_file).split('.', 1)[0]

tree = ET.parse(dat_file)
root = tree.getroot()
games = root.findall('.//game')

game = next(filter(lambda g: g.get('name') == target_file_name, games), None)

if game is None:
    print(f'Game {target_file_name} not found in {dat_file}')
    sys.exit(1)

with zipfile.ZipFile(target_file, 'r') as zip:
    roms = game.findall('rom')

    for rom in tqdm.tqdm(roms):
        name = rom.get('name')
        size = int(rom.get('size'))
        crc = int(rom.get('crc'), 16)
        sha1 = rom.get('sha1')

        ze = zip.getinfo(name)

        if ze.file_size != size:
            print(f'{name} size mismatch: expected {size}, got {ze.file_size}')
            sys.exit(1)
        
        with zip.open(name) as f:
            m = hashlib.sha1()

            for chunk in iter(lambda: f.read(4096), b''):
                m.update(chunk)
            
            if m.hexdigest() != sha1:
                print(f'{name} sha1 mismatch: expected {sha1}, got {m.hexdigest()}')
                sys.exit(1)

sys.exit(0)