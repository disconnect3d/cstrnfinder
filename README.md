# cstrnfinder: finding stupid bugs

This is a repository for a "cstrnfinder" research, where I searched lots of code and found 50+ stupid bugs(?) related to how C strings are compared against string literals with (sometimes) incorrect hardcoded size argument.

I presented this research (along with other things) on [A Midwinter Night's Con - 2020](https://absoluteappsec.com/cons/midwinter-2020/). You can [find the slides here](https://docs.google.com/presentation/d/1VpXqzPIPrfIPSIiua5ClNkjKAzM3uKlyAKUf0jBqoUI) or [watch the talk here](https://www.youtube.com/watch?v=-xVBd8MGlJs). If you want to discuss it more, reply to this [tweet](https://twitter.com/disconnect3d_pl/status/1339757359896408065).

This project was created during IRAD time at Trail of Bits, along with the small "blog post" below :).

For a list of reported or fixed bugs, scroll to the `Reported or fixed bugs` section.

* There is also a version for binaries made as a [Binary Ninja plugin created by murx-](https://github.com/murx-/cstrnfinder)

### TL;DR: I want to run cstrnfinder

Either grep for strn* functions and use the cstrnfinder.py script:
```
Manual search:
    egrep -Ri '(strncmp|strnicmp|strncat|stpncpy|strncpy|strncasecmp|memcmp|memcpy|memmove|mempcpy|wmemcpy|wmemmove|wmempcpy|bcopy|bcmp)[ ]?[(].*[)]' . > ../findings
And then:
    cat ../findings | python cstrnfinder.py | grep XXX
Or grep for YYY or for ZZZ
```

or use the CodeQL query described in this README.

## How it started

Reading some C code I started wondering about how we use string literals with string comparison and other functions. For example, when we want to check if a given C-string starts with another one there is no `startswith` function and we have to use the `strncmp` function instead:

```c
int strncmp(const char *s1, const char *s2, size_t n);
```

Which accepts the two C-strings and the number of bytes we want to compare. So we could use it like this:

```c
strncmp(some_cstring, "prefix_", 7);
```

This isn’t very convenient and… may introduce bugs.

## Size is the issue
So this function allows for passing any size no matter what is the length of the two argument strings. This might be handy, but would also accept mistakes. One of such that can also be easily detected, is a case when one of the arguments is a string literal and the size passed is smaller then the length of the string. And this is what the cstrnfinder project was created for.

## Initial search
I initially looked for bugs manually and via simple greps:
```
git grep -i 'strncmp[ ]?[(].*[)]' > "$RESULTS_PATH/strncmp"
git grep -i 'strnicmp[ ]?[(].*[)]' > "$RESULTS_PATH/strnicmp"
git grep -i 'strncat[ ]?[(].*[)]' > "$RESULTS_PATH/strncat"
git grep -i 'strncpy[ ]?[(].*[)]' > "$RESULTS_PATH/strncpy"
git grep -i 'memcmp[ ]?[(].*[)]' > "$RESULTS_PATH/memcmp"
git grep -i 'strncasecmp[ ]?[(].*[)]' > "$RESULTS_PATH/strncasecmp"
```
accompanied with a script that parsed the output of `str*` function calls, filtered the ones that used a string literal as an argument and checked its length against the size argument. And I downloaded ~300 different C codebases manually to look for those. I found some bugs but I also needed a more scalable solution.

## Meet Google BigQuery
I reminded myself of a [LiveOverflow’s yt video about finding bitcoin keys in GitHub repos through Google BigQuery](https://www.youtube.com/watch?v=Xml4Gx3huag). I started playing with Google BigQuery and used its `bigquery-public-data.github_repos` tables. As of the time writing this, this dataset was last updated on 20th of March 2020 and contains data from 2.5M repositories. The "contents" table which holds the text files (and so code) has 274GB of data.

## The query
I wrote the query shown below to find all `str*` calls in all GitHub repositories. Note that the `lines` column is an array of all `str*` function calls. Iirc it doesn’t matter if it was in one line or span across many lines.

```
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

## The weird regex
The used regex can be inspected on [regexper.com](https://regexper.com/#%28%28%3F%3Astrncmp%7Cstrnicmp%7Cstrncat%7Cstrncpy%7Cmemcmp%7Cstrncasecmp%7Cstpncpy%7Cstrncpy%29%5Cs*%5C%28%28%3F%3A%5B%5E%28%29%5D*%5C%28%28%3F%3A%5B%5E%28%29%5D*%5C%28%28%3F%3A%5B%5E%28%29%5D*%5C%28%28%3F%3A%5B%5E%28%29%5D*%5C%28%28%3F%3A%5B%5E%28%29%5D*%5C%28%5B%5E%28%29%5D*%5C%29%29*%5B%5E%28%29%5D*%5C%29%29*%5B%5E%28%29%5D*%5C%29%29*%5B%5E%28%29%5D*%5C%29%29*%5B%5E%28%29%5D*%5C%29%29*%5B%5E%28%29%5D*%5C%29%29).

The regex would catch, iirc 5-6 recursive calls in arguments passed to `str*` functions, so it is rather needlessly exhaustive. This is done a bit “weird” due to the fact regexes usually can’t match balanced parentheses… This is out of topic, but the .NET regex engine can match balanced parentheses through its [“balancing groups” feature](https://stackoverflow.com/a/35271017).

## The result set
The query finds all `str*` calls in all GitHub repositories so there are 33M files that contain the findings, so there are even more results, which number I haven’t checked. Filtering the findings by those that use a string literal argument and a number literal size argument gives “only” 2M results. Filtering further by those when the size is less than the string literal length gives 372K results. However, in reality, there are tons of duplicates from forks, indirect forks and from vendoring dependencies.

I narrowed down the results to 11.8k records by filtering out the duplicates. I did this by taking only the entry/finding from the most starred repositories. I took the repository stars information from [`githubarchive` dataset](https://stackoverflow.com/questions/42918135/how-to-get-total-number-of-github-stars-for-a-given-repo-in-bigquery) and assumed that two findings were duplicates when their content and part of its path (its last directory and its filename) matched.

I still haven’t gotten through all the results and a lot of them are false positives. Let me give some examples:

```
strncmp(rendererString, "Mali-4xx", 6)   strlen=8, n=6
strncmp(rendererString, "Adreno (TM) 2xx", 13)   strlen=15, n=13
strncmp(rendererString, "Adreno 2xx", 8)   strlen=10, n=8

strncmp(d, "1 RSA", 2)   strlen=5, n=2
strncmp(d, "2 DH", 2)   strlen=4, n=2
strncmp(d, "3 DSA", 2)   strlen=5, n=2

strncmp (argv[1], "-help", 2)   strlen=5, n=2
strncmp(argv[n],"-debug", 2)   strlen=6, n=2
strncmp(argv[n],"-verbose", 2)   strlen=8, n=2
```

As we can see, often a longer string literal then the size argument is passed, either for easier understanding or readability of the code. I think that this is not good because then it is not easy to reason about the use case in an automated way. I think only the prefix string literal should be passed and a full context could be given e.g. in a comment.

## Bugs != vulnerabilities
A lot of bugs found that way are not security vulnerabilities. Though, it is possible there are some vulns like this. This could be:

* When a path is matched without its ending `/` character: `strncmp(var, “path/”, 4)`
* When an extension is incorrectly matched: `strncmp(var, “.exe”, 3)` and e.g. not filtered
* When parsing some format and mismatching some syntax due to wrong size
* When your other if branch is not reachable due to previous incorrect match ([almost a thing here](https://github.com/SerenityS/android_kernel_lge_g3/blob/lollipop/drivers/misc/tspdrv/touch_fops.c#L92-L98) - though they still do not unset the `IMMR_DEB` flag):
```c
if (strncmp(buf, “debugon”, 5) == 0) { IMMR_DEB = true; }
else if (strncmp(buf, “debugoff”, 8) == 0) { …}
```

## Reported or fixed bugs
As said previously, a lot of the findings are false positives, as they are e.g. parsing command line optional arguments. However, I was still able to find a lot of bugs in various projects and reported and/or fixed them:

* [Linux kernel - Fix off by one in tools/perf strncpy size argument](https://lore.kernel.org/lkml/20200309104855.3775-1-dominik.b.czarnota@gmail.com/)
* [Linux kernel - Fix off by one in samsung driver strncpy size arg](https://lore.kernel.org/lkml/20200309152250.5686-1-dominik.b.czarnota@gmail.com/)
* [Linux kernel - Fix off by one in nvidia driver strncpy size arg](https://lore.kernel.org/lkml/20200309124947.4502-1-dominik.b.czarnota@gmail.com/)
* [GCC 10.x (trunk) - 2 issues: write_only and read_write attributes can be mistyped due to invalid strncmp size argument](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=93640)
* [GCC 10.x (trunk) - 3 not triaged issues](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=93641)
* [PostgreSQL’s `json_to_tsvector` mistyped types](https://www.postgresql.org/message-id/CABEVAa1dU0mDCAfaT8WF2adVXTDsLVJy_izotg6ze_hh-cn8qQ%40mail.gmail.com) - [PoC here](https://gist.github.com/disconnect3d/dcfccfc1102c4f46417f5e71922aacea)
* [google/google-input-tools - off-by-ones when parsing XML comments](https://github.com/google/google-input-tools/pull/17), initially reported to Google via https://www.google.com/appserve/security-bugs/
* [facebook/redex - missing “/” character](https://github.com/facebook/redex/pull/473)
* [opensource-apple/dyld - incorrect path check in ImageLoaderMachO](https://github.com/opensource-apple/dyld/pull/4), initially reported to [darlinghq/darling](https://github.com/darlinghq/darling/pull/737)
* [znc/znc - incorrect HTML entities parsing](https://github.com/znc/znc/pull/1715)
* [MariaDB/server - incorrect “--parent-pid” flag check](https://github.com/MariaDB/server/pull/1502)
* [OpenRC/openrc - could be a null pointer dereference?](https://github.com/OpenRC/openrc/pull/361) and the same [here](https://github.com/OpenRC/openrc/pull/362)
* [FreeRADIUS/freeradius-server - fix rlm_cache_sanity check for crazy people](https://github.com/FreeRADIUS/freeradius-server/pull/3370)
* [karelzak/util-linux - “/dev/mapper/” path check off by one](https://github.com/karelzak/util-linux/pull/1007)
* [Radare2 - 6 various issues](https://github.com/radareorg/radare2/pulls?q=is%3Apr+author%3Adisconnect3d+is%3Aclosed)
* [xbmc/xbmc - XML settings incorrect parsing](https://github.com/xbmc/xbmc/pull/17355)
* [bhro/plan9 - off by one in “/fd/” path check](https://github.com/brho/plan9/pull/3)
* [shirobu2400/mmdpi - off by one file extension checks](https://github.com/shirobu2400/mmdpi/pull/3)
* [haxelime/lime - off by one when matching JNI class name](https://github.com/haxelime/lime/pull/1392)
* [RIOT-OS/RIOT - off by one in command parsing](https://github.com/RIOT-OS/RIOT/pull/13859)
* [SerenityS/android_kernel_lge_g3 - incorrect debug flag handling in an android driver](SerenityS/android_kernel_lge_g3)
* [chrisosaurus/icarus - incorrect “String” token parsing in a programming language](https://github.com/chrisosaurus/icarus/pull/1)
* [lammps/lammps - not full string matched](https://github.com/lammps/lammps/pull/1991)
* [pear/HTTP_WebDAV_Server - `HTTP_CONTENT` header name off by one](https://github.com/pear/HTTP_WebDAV_Server/pull/4)
* [velnias75/NetMauMau - fix incorrect “/favicon.ico” string match](https://github.com/velnias75/NetMauMau/pull/40)
* [realnc/qdats - some off by one “true” value](https://github.com/realnc/qtads/pull/10)
* [OMENScan/Achoir - off by one when checking for “/DRV:” string](https://github.com/OMENScan/AChoir/pull/9)
* [nanomsg/nng - Fix message realloc test off by one str comparison](https://github.com/nanomsg/nng/pull/1234)
* [nntop/nDPI - Fix off by one when checking for "GET / HTTP" string](https://github.com/ntop/nDPI/pull/868) and [Fix incorrect "<iq from=\"' parsing](https://github.com/ntop/nDPI/pull/869)
* [nzbget/nzbget - http:/ vs http:// off by one, not sure if real bug](https://github.com/nzbget/nzbget/pull/679)
* [Enlightenment/enlightenment - off-by-one when checking for `"LDR_"` envvar prefix](https://github.com/Enlightenment/enlightenment/pull/7)
* [brianmario/yajl-ruby - "false" off-by-one](https://github.com/brianmario/yajl-ruby/pull/197)
* [nginx/njs - off-by-3 during parsing a "base64url" string](https://github.com/nginx/njs/pull/363)
* https://github.com/martinpitt/umockdev/pull/114
* https://github.com/JetBrains/jdk8u_jdk/pull/33
* https://github.com/martinpitt/umockdev/pull/114
* https://github.com/Arakula/f9dasm/pull/17
* https://github.com/HDF-NI/hdf5.node/pull/116
* https://github.com/ColinIanKing/stress-ng/pull/93

The list will get bigger and bigger as I still haven’t gone through all the results list.

## What is next
The approach taken may still miss a lot of bugs. For example, it doesn’t detect cases when the size argument passed to a `str*` function is calculated via `strlen` or `sizeof` functions and then incorrectly subtracted (too much). Similarly, if the string literal is assigned to a `const char*` variable previously or comes from a `#define` such cases will also be missed.

However, we can still find those if we use a more advanced tool such as CodeQL. In one sentence, CodeQL allows us to “query” a given codebase in an SQL-like language and write queries that can find bugs. Some of its automated reasoning can be found in http://lgtm.com/. 

## CodeQL query
I have written the CodeQL query that can detect the described issues, as shown below. Apart from the previous method, this query can also detect cases when:

* The string literal comes from a const char* variable
* The size argument is a result of sizeof() call subtracted by a number literal
* The size argument or the string literal comes from a macro

However, it could still be improved to e.g. find non constant variables too or to use a local variables data analysis to see if the size argument mismatches the length of the passed string literal (or a string argument, assuming there are cases when we could deduce its length).

```
import cpp
predicate onlyStrNFunctions(FunctionCall call) {
 call.getTarget().getName() in [
   "strncmp", "strnicmp", "strncat", "stpncpy", "strncpy", "strncasecmp",
   "memcmp", "memcpy", "memmove", "mempcpy",
   "wmemcpy", "wmemmove", "wmempcpy",
   "bcopy", "bcmp"
 ]
}
int getConstantInt(Expr e) {
 result = e.getValue().toInt()
}
predicate getExprAndStrArguments(FunctionCall call, int argIndex1, int argIndex2, Expr resultExpr, string resultString) {
 (resultExpr = call.getArgument(argIndex1) and resultString = call.getArgument(argIndex2).getValue())
 or
 (resultExpr = call.getArgument(argIndex2) and resultString = call.getArgument(argIndex1).getValue())
}
from FunctionCall call, Expr exprArg, string strArg, int sizeArg
where
 onlyStrNFunctions(call)
 and getExprAndStrArguments(call, 0, 1, exprArg, strArg)
 and sizeArg = getConstantInt(call.getArgument(2))
 and strArg.length() > sizeArg
select call, exprArg, strArg, sizeArg
```

## Random funny aspect
Well, all the bitcoin forks seem to just fire sed replace & have the same potential issues...

```
➜  cstrnfinder git:(master) ✗ cat results_GCP | grep 'XXX' | grep 'qt/bitcoin' | uniq | wc -l
      49
➜  cstrnfinder git:(master) ✗ cat results_GCP | grep 'XXX' | grep 'qt/bitcoin' | uniq | head
grantcoin/grantcointest9:src/qt/bitcoin.cpp:      [XXX] strncasecmp(argv[i], "grantcoin:", 7)   strlen=10, n=7
smith7800/brightcoin:src/qt/bitcoin.cpp:      [XXX] strncasecmp(argv[i], "slimcoin:", 7)   strlen=9, n=7
Bitspender/Tamcoin-v2:src/qt/bitcoin.cpp:      [XXX] strncasecmp(argv[i], "Tamcoin:", 7)   strlen=8, n=7
stronghands/stronghands:src/qt/bitcoin.cpp:      [XXX] strncasecmp(argv[i], "stronghands:", 7)   strlen=12, n=7
JoseBarrales/lendcoin:src/qt/bitcoin.cpp:      [XXX] strncasecmp(argv[i], "paycoin:", 7)   strlen=8, n=7
bitgrowchain/bitgrow:src/qt/bitcoin.cpp:      [XXX] strncasecmp(argv[i], "bitgrow:", 7)   strlen=8, n=7
lomocoin/lomocoin-qt:src/qt/bitcoin.cpp:      [XXX] strncasecmp(argv[i], "lomocoin:", 7)   strlen=9, n=7
rcoinwallet/RCoinUSA:src/qt/bitcoin.cpp:      [XXX] strncasecmp(argv[i], "RCoinUSA:", 7)   strlen=9, n=7
5mil/space:src/qt/bitcoin.cpp:      [XXX] strncasecmp(argv[i], "Spaceballz:", 7)   strlen=11, n=7
sengmangan/XPAY:src/qt/bitcoin.cpp:      [XXX] strncasecmp(argv[i], "paycoin:", 7)   strlen=8, n=7
```

