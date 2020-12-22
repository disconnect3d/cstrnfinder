SELECT
  files.repo_name,
  files.path,
  contents.content,
  contents.lines
FROM
  `bigquery-public-data.github_repos.sample_files` files
JOIN (
  SELECT
    id,
    content,
    REGEXP_EXTRACT_ALL(content, r'[}].*[\n]') as lines
    #REGEXP_EXTRACT_ALL(content, r'Free Software Foundation.*[\n]') as line
    
  FROM
    `bigquery-public-data.github_repos.sample_contents`
  WHERE
    REGEXP_CONTAINS(content, r'Free Software Foundation')
  ) contents
ON
  files.id = contents.id
WHERE
  files.repo_name = 'redbrain/gccpy' AND files.path = 'libstdc++-v3/testsuite/25_algorithms/merge/check_type.cc'
