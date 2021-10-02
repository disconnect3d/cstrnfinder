SELECT
  files.repo_name,
  files.path,
  contents.content,
  contents.lines
FROM
  `bigquery-public-data.github_repos.files` files
JOIN (
  SELECT
    id,
    content,
    REGEXP_EXTRACT_ALL(
      content,
      r'((?:strncmp|strnicmp|strncat|strncpy|memcmp|strncasecmp|stpncpy|strncpy)\s*\((?:[^()]*\((?:[^()]*\((?:[^()]*\((?:[^()]*\((?:[^()]*\([^()]*\))*[^()]*\))*[^()]*\))*[^()]*\))*[^()]*\))*[^()]*\))')
    as lines    
  FROM
    `bigquery-public-data.github_repos.contents`
  WHERE
    REGEXP_CONTAINS(content, r'(strncmp|strnicmp|strncat|strncpy|memcmp|strncasecmp|stpncpy|strncpy)')
  ) contents
ON
  files.id = contents.id
