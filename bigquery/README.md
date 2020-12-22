### Query for cstrnfinder

Note that it has a finite complexity of function calls but its unlikely any func call is more complex then the one present here. And we usually don't want to find complex calls.

```sql
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
```


### Query to get Github repos with stars (approximately)

Note that we use a `WatchEvent` here.

```sql
SELECT repo.name AS repo_with_stars, APPROX_COUNT_DISTINCT(actor.id) stars 
FROM `githubarchive.month.*` 
WHERE type='WatchEvent'
GROUP BY 1
```
