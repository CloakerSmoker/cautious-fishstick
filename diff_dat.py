
import sys, os, hashlib, zipfile, pathlib
import xml.etree.ElementTree as ET
import tqdm

shadow_dir = sys.argv[1]
base_dir = sys.argv[2]

xml_file = sys.argv[3]

tree = ET.parse(xml_file)

root = tree.getroot()
games = root.findall('.//game')

class FileInfo:
    def __init__(self, name, size, crc):
        self.name = name
        self.size = size
        self.crc = crc
    
    def __eq__(self, value):
        return self.name == value.name and self.size == value.size and self.crc == value.crc

class ArchiveInfo:
    def __init__(self, name, children, force_bad=False):
        self.name = name
        self.children = children
        self.force_bad = force_bad
    
    def __eq__(self, value):
        if len(self.children) != len(value.children):
            return False

        for crc in self.children:
            if not crc in value.children:
                return False
        
        return True
    
dat_files = {}

for game in tqdm.tqdm(games):
    roms = game.findall('rom')

    children = {}
    force_bad = False

    for rom in roms:
        try:
            name = rom.get('name')
            size = int(rom.get('size'))
            crc = int(rom.get('crc'), 16)

            children[crc] = FileInfo(name, size, crc)
        except:
            print(f"Error processing {rom.get('name')} in {game.get('name')}")
            print(rom)

            force_bad = True

    name = game.get('name')
    dat_files[name] = ArchiveInfo(name, children, force_bad)

existing_files = {}

index = 0

for file_name in tqdm.tqdm(os.listdir(base_dir)):
    zf = zipfile.ZipFile(base_dir + file_name)
    
    children = {}

    for ze in zf.infolist():
        children[ze.CRC] = FileInfo(ze.filename, ze.file_size, ze.CRC)

    name = file_name.replace('.zip', '')
    existing_files[name] = ArchiveInfo(name, children)

    index += 1

    #if index > 30:
    #    break

present = []
missing = []
bad = []
deleted = []
renamed = {}

for name, info in dat_files.items():
    if info.force_bad:
        print('F', info.name)
        bad.append(info)
        continue

    existing_info = existing_files.get(name, None)

    if not existing_info:
        # Check if there's a file with the same content but different name

        matching_identity_infos = [existing_info for existing_info in existing_files.values() if existing_info == info]

        if len(matching_identity_infos):
            # name not found, identity found

            print('R', info.name)
            renamed[matching_identity_infos[0].name] = info.name
        else:
            # name not found, identity not found

            print('M', info.name)
            missing.append(info)
    else:
        if existing_info != info:
            # name found, identity doesn't match

            print('B', info.name)
            bad.append(info)
        else:
            # name found, identity matches

            print('P', info.name)
            present.append(info)

for name, info in existing_files.items():
    if name not in dat_files and name not in renamed:
        print('D', info.name)
        deleted.append(info.name)

os.makedirs(shadow_dir, exist_ok=True)
open(shadow_dir + '/present.txt', 'w').write('\n'.join([f"{f.name}" for f in present]))
open(shadow_dir + '/missing.txt', 'w').write('\n'.join([f"{f.name}" for f in missing]))
open(shadow_dir + '/bad.txt', 'w').write('\n'.join([f"{f.name}" for f in bad]))
open(shadow_dir + '/deleted.txt', 'w').write('\n'.join(deleted))
open(shadow_dir + '/renamed.txt', 'w').write('\n'.join([f"{old} -> {new}" for old, new in renamed.items()]))