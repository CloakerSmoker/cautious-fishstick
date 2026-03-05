

import asyncio
import os
import select
import sys, subprocess, sqlite3, json, glob
import tqdm

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
        self.process.stdin.close()

class zipfinder:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.directory_queue = [data_dir]
        self.zip_queue = []
    
    def get_more_work(self):
        while len(self.zip_queue) == 0 and len(self.directory_queue) > 0:
            for entry in os.scandir(self.directory_queue.pop(0)):
                if entry.is_dir():
                    self.directory_queue.append(entry.path)
                elif entry.is_file() and entry.name.lower().endswith('.zip'):
                    self.zip_queue.append(os.path.relpath(entry.path, self.data_dir))

        return self.zip_queue.pop() if len(self.zip_queue) > 0 else None
        

def main(threads, data_dir):
    workers = []

    for i in range(threads):
        workers.append(zipper())

    index = 0

    zips = zipfinder(data_dir)

    workers_stdout = [worker.process.stdout for worker in workers]
    workers_stderr = [worker.process.stderr for worker in workers]
    workers_stdin = [worker.process.stdin for worker in workers]
    workers_jobs_in_flight = [0] * len(workers)
    workers_done = [False] * len(workers)
    workers_lines = [''] * len(workers)

    while any(worker.process.poll() is None for worker in workers):
        readable_output, _, _ = select.select(workers_stdout, [], [], 0.1)
        readable_debug, _, _ = select.select(workers_stderr, [], [], 0.1)

        for _ in range(30):
            for i in range(len(workers)):
                if workers_jobs_in_flight[i] < 10 and not workers_done[i]:
                    job = zips.get_more_work()

                    if not job:
                        print(f"No more jobs to assign to worker {i}")
                        workers_done[i] = True
                        break

                    if conn.execute('SELECT 1 FROM files WHERE path = ?', (job,)).fetchone():
                        continue

                    print(f"Assigning job {job} to worker {i}")

                    workers[i].queue(os.path.join(data_dir, job))
                    workers_jobs_in_flight[i] += 1

        for stdout in readable_output:
            while len(select.select([stdout], [], [], 0)[0]):
                worker_index = workers_stdout.index(stdout)

                line = stdout.readline().strip()

                if line == '':
                    # EOF reached for this worker
                    break

                #print(f"Zipper output: {line}")

                if line:
                    workers_jobs_in_flight[worker_index] -= 1

                    if workers_jobs_in_flight[worker_index] == 0 and workers_done[worker_index]:
                        print(f"Worker {worker_index} has completed all jobs")
                        workers_stdin[worker_index].close()

                    print(workers_jobs_in_flight)

                    #print(workers_busy)

                    try:
                        print(f"{worker_index}: {line}")

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
                                ''', (zip_id, entry['name'], entry['size'], entry['crc'], '', entry['sha1']))

                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON from zipper output: {e}")
                        print(f"Line: {line}")
        
        for stderr in readable_debug:
            while len(select.select([stderr], [], [], 0)[0]):
                line = stderr.readline().strip()

                if line == '':
                    # EOF reached for this worker
                    workers_stderr.remove(stderr)
                    break

                if line:
                    #print(f"Zipper debug: {line}")
                    pass

        conn.commit()

main(int(sys.argv[1]), sys.argv[2])