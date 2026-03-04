

import asyncio
import os
import select
import sys, subprocess, sqlite3, json, glob

conn = sqlite3.connect('hashes.db')

conn.execute('''
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    size INTEGER,
    sha256 TEXT
);
''')

conn.execute('''
CREATE TABLE IF NOT EXISTS files_errors (
    path TEXT PRIMARY KEY,
    error TEXT
);
''')

conn.execute('''
CREATE TABLE IF NOT EXISTS entries (
    zip_id INTEGER,
    name TEXT,
    size INTEGER,
    crc TEXT,
    md5 TEXT,
    sha1 TEXT,
             
    PRIMARY KEY (zip_id, name)
);
''')

conn.execute('''
CREATE TABLE IF NOT EXISTS entries_errors (
    zip_id INTEGER,
    name TEXT,
    error TEXT,
             
    PRIMARY KEY (zip_id, name)
);
''')

class zipper:
    def __init__(self):
        self.process = subprocess.Popen(['./zipper.elf'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def queue(self, zip_path):
        self.process.stdin.write(zip_path + '\n')
        self.process.stdin.flush()
    
    def end_queue(self):
        self.process.stdin.write('\n')
        self.process.stdin.flush()
    
    def read_results(self):
        if self.process.poll() is not None:
            raise Exception("Zipper process has exited")
        
        output = []

        while True:
            ready, _, _ = select.select([self.process.stdout], [], [], 0.1)

            if ready:
                line = self.process.stdout.readline()

                if not line:
                    break

                output.append(line.strip())
            else:
                break
        
        return output

def main(threads, data_dir):
    workers = []

    for i in range(threads):
        workers.append(zipper())

    index = 0

    for zip_path in glob.glob('**/*.zip', root_dir=data_dir, recursive=True):
        zip_path = os.path.join(data_dir, zip_path)

        if conn.execute('SELECT 1 FROM files WHERE path = ?', (zip_path,)).fetchone():
            continue

        workers[index % threads].queue(zip_path)
        index += 1
    
    for worker in workers:
        worker.end_queue()

    workers_stdout = [worker.process.stdout for worker in workers]
    workers_stderr = [worker.process.stderr for worker in workers]

    while any(worker.process.poll() is None for worker in workers):
        for worker in workers:
            readable_output, _, _ = select.select(workers_stdout, [], [], 0.1)
            readable_debug, _, _ = select.select(workers_stderr, [], [], 0.1)

            for stdout in readable_output:
                line = stdout.readline().strip()

                print(f"Zipper output: {line}")

                if line:
                    try:
                        result = json.loads(line)

                        result['path'] = os.path.relpath(result['path'], data_dir)

                        if 'error' in result:
                            print(f"Error processing {result['path']}: {result['error']}")

                            conn.execute('INSERT OR REPLACE INTO files_errors (path, error) VALUES (?, ?)', (result['path'], result['error']))
                            continue

                        zip_id = conn.execute('INSERT OR REPLACE INTO files (path, size, sha256) VALUES (?, ?, ?) RETURNING ROWID', (result['path'], result['size'], result['sha256'])).fetchone()[0]

                        for entry in result['entries']:
                            if 'error' in entry:
                                print(f"Error processing entry {entry['name']} in {result['path']}: {entry['error']}")

                                conn.execute('INSERT OR REPLACE INTO entries_errors (zip_id, name, error) VALUES (?, ?, ?)', (zip_id, entry['name'], entry['error']))
                            else:
                                conn.execute('''
                                    INSERT OR REPLACE INTO entries (zip_id, name, size, crc, md5, sha1)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                ''', (zip_id, entry['name'], entry['size'], entry['crc'], entry['md5'], entry['sha1']))

                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON from zipper output: {e}")
                        print(f"Line: {line}")
            
            for stderr in readable_debug:
                line = stderr.readline().strip()

                if line:
                    print(f"Zipper debug: {line}")

        conn.commit()

main(int(sys.argv[1]), sys.argv[2])