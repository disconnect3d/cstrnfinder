import csv
import glob
import json
import pickle
from collections import defaultdict

from tqdm import tqdm

from cstrnfinder import parse_line, check_all

# Findings cache to remove files + code lines duplicates
# doing it because we got like ~33kk results and tons of them are duplicates
# like repository forks or the same 3rd party lib copied around into many projects
#
# key = (dir_and_file, result)
# value = (repo_path)
findings = {}

# Get a dict of GitHub repo stars
# for the used query, see ./bigquery/README.md
print('Loading github-repo-stars.csv')
c = csv.reader(open('./github-repo-stars.csv'))
# skip header
assert next(c) == ['repo_with_stars', 'stars']
repo_stars = dict((i[0], int(i[1])) for i in c)
print('Loaded repo_stars')

funcs_to_find = check_all

dir_and_file = lambda filepath: '/'.join(filepath.split('/')[-2:])

for filepath in tqdm(glob.glob('./gcp-results/*'), desc="File"):
    with open(filepath) as f:
        for line in tqdm(f, desc="Lineno"):
            record = json.loads(line)

            #print(record['repo_name'], record['path'])
            #record.keys() == 'repo_name', 'path', 'lines'
            for finding in record['lines']:
                for func in funcs_to_find:
                    if func not in finding:
                        continue
                    else:
                        # parse_line returns string prefixed with [XXX] for most-likely bugs and [YYY], [ZZZ] or [QQQ] for others
                        res = parse_line(finding, func, skip_prefix=True)
                        if res:
                            # See comment below
                            #if res[:5] in ('[XXX]', '[YYY]', '[QQQ]', '[ZZZ]'):
                            #        print("%s:%s:      %s" % (record['repo_name'], record['path'], res))

                            # Find only XXX for now as its the most interesting thing.
                            if res[:5]  == '[XXX]':
                                key = (dir_and_file(record['path']), res)
                                #print("%s:%s:      %s" % (record['repo_name'], record['path'], res))

                                curr_repo = findings.get(
                                    key, (-2, '')
                                )

                                repo_name = record['repo_name']

                                findings[key] = max(
                                    curr_repo,
                                    (repo_stars.get(repo_name, -1), repo_name)
                                )

with open('findings', 'wb') as f:
    pickle.dump(findings, f)
