
import sys, glob, os, shlex
import xml.etree.ElementTree as ET

shadow_dir = sys.argv[1]
dats_dir = sys.argv[2]
data_dir = sys.argv[3]

missing = open('missing.txt', 'w')

for dat in glob.glob('**/*.dat', root_dir=dats_dir, recursive=True):
    dat_path = os.path.join(dats_dir, dat)
    dat_info = ET.parse(dat_path).getroot()

    dat_name = dat_info.find('.//header').find('name').text

    dat_directory = os.path.dirname(dat) + '/' + dat_name
    dat_shadow = os.path.join(shadow_dir, dat_directory)
    dat_data = os.path.join(data_dir, dat_directory)

    if os.path.exists(dat_shadow + '/present.txt'):
        print(f'{dat_shadow} already exists, skipping')
        continue

    if not os.path.exists(os.path.join(data_dir, dat_directory)):
        print(f'Directory {dat_directory} not found, skipping')
        missing.write(f'{dat_directory}\n')
    else:
        print(f'Comparing {dat_directory}')
        #print(f'python diff_dat.py {shlex.quote(dat_shadow)} {shlex.quote(dat_data + "/")} {shlex.quote(dat_path)}')
        #break
        os.system(f'python diff_dat.py {shlex.quote(dat_shadow)} {shlex.quote(dat_data + "/")} {shlex.quote(dat_path)}')


