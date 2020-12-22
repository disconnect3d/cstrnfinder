"""
Manual search:
    egrep -Ri '(strncmp|strnicmp|strncat|stpncpy|strncpy|strncasecmp|memcmp|memcpy|memmove|mempcpy|wmemcpy|wmemmove|wmempcpy|bcopy|bcmp)[ ]?[(].*[)]' . > ../findings

And then:
    cat ../findings | python cstrnfinder.py | grep XXX

Or grep for YYY or for ZZZ
"""
import os
import re
import ast


def findme(prefix, string):
    r = re.compile('(%s)[ ]*[(]' % prefix)

    # Just needed for later finding of function arguments position
    prefix += '('

    for line in string.splitlines():
        # Change all cases of '<prefix>    (' into '<prefix>('
        # to catch more samples
        line = r.sub('\\1(', line)

        try:
            res = parse_line(line, prefix)
            if res:
                print(res)
        except Exception as e:
            print('[XXXEXC] %r occured for line=%r' % (e, line))


def debug_line(line, prefix):
    """The complete flow from above but for one line; for debugging obviously"""
    assert prefix[-1] != '('
    print("LINE   : %r" % line)
    print("PREFIX : %r" % prefix)
    r = re.compile('(%s)[ ]*[(]' % prefix)
    prefix += '('
    line = r.sub('\\1(', line)
    parse_line(line, prefix)


def parse_line(line, prefix, skip_prefix=False):

        if not skip_prefix:
            # Lower the line to catch custom functions like 'UniStrncmp'
            line = line.lower()

            # Sanity check - this should not happen (meaning the input file is broken)
            if prefix not in line:
                #raise Exception('prefix %r not in line: %r' % (prefix, line))
                return '[ERR] prefix %r not in line: %r' % (prefix, line)

            idx = line.find(prefix)
            idx += len(prefix)
        else:
            idx = line.index('(')

        haystack = line[idx:]
        end_paren_idx = -1
        parens = 1
        #print(line)
        for i, ch in enumerate(haystack):
            #print(i, ch)
            if ch == '(':
                parens += 1
                #print("Parens++")
            elif ch == ')':
                if parens == 1:
                    #print("Found! Break")
                    end_paren_idx = i + idx
                    break
                else:
                    parens -= 1
                    #print("Parens--")
        needle = line[idx:end_paren_idx]
        if not needle:
            #print("[!] Skipping line %r" % line)
            return
        #print(line)
        #print('NEEDLE:', needle)
        # Silly one
        try:
            arg1, arg2, n = needle.split(',')
        except ValueError as e:
            # Bail out
            return '!!! VALUEERROR: line=%r, needle=%r' % (line, needle)

        arg1 = arg1.strip()
        arg2 = arg2.strip()
        n = n.strip()
        #print('$$$$ arg1=%r arg2=%r n=%r' % (arg1, arg2, n))

        try:
            n = int(n)
        except ValueError:
            return "[!] n=%r not const int in line=%r" % (n, line)

        # Not the best solution, does not support arguments like '"\\xf"' as in Python it should be '"\\x0f"' :/
        # (in other words, a given hex-encoded byte needs two characters)
        replace_escaped_chars = ast.literal_eval

        def remove_cast(string):
            """
            Hope this works in all those ugly cases, eh?

            The idea is to go from right to left and take the "string", though we have to remember
            about special chars like '\"'
            """
            assert string[-1] == '"'
            for i in range(len(string)-2, 0, -1):   # for 'abc' this will only give index of 'b'
                if string[i] == '"' and string[i-1] != '\\':
                    return string[i:]

            # This should not happen
            raise Exception("Can't remove cast from %s - wtf?" % string)

        if len(arg1) == 0 or len(arg2) == 0:
            return '[ERR] bad arg len; line=%r, arg1=%r, arg2=%r, n=%r' % (line, arg1, arg2, n)

        try:
            if arg1[0] == '"' and arg1[-1] == '"':
                arg1 = replace_escaped_chars(arg1)
                length = len(arg1)

            elif arg2[0] == '"' and arg2[-1] == '"':
                arg2 = replace_escaped_chars(arg2)
                length = len(arg2)

            # This is a ridiculous case where arg1 or arg2 are casted to some cstring pointer.. like: '(fancychar*)"wtf"'
            # Example from Nginx:
            #   ngx_strncasecmp(h->value.data, (u_char *) "bytes=", 6)
            elif arg1[0] == '(' and arg1[-1] == '"':
                arg1 = remove_cast(arg1)
                arg1 = replace_escaped_chars(arg1)
                length = len(arg1)
                
            elif arg2[0] == '(' and arg2[-1] == '"':
                arg2 = remove_cast(arg2)
                arg2 = replace_escaped_chars(arg2)
                length = len(arg2)
                
            else:
                return "[!] arg1 and arg2 are not const char*: %r %r %r" % (arg1, arg2, line)
        except SyntaxError as e:
            return '[QQQ] SyntaxErr: line=%r' % line
        except Exception as e:
            return '[QQQ] UnknownErr: exc=%s line=%r' % (e, line)

        # Possibly bug - cases where we mismatch `size_t n` with real const char* C-string length:
        # Example:
        #   strncmp(opt, "eee_timer:", 6)   - the `n` should rather be `strlen("eee_timer:")` or 7 or (maybe) `strlen(opt)`
        if length > n:
            return '[XXX] %s   strlen=%d, n=%d' % (line, length, n)

        # Rather okay - cases where the `n` takes into account the null byte - should probably be only memcmp?
        # Example:
        #   memcmp("intxblk", pbuf, 8)  - this compares bytes: intxblk\0 with the variable pbuf
        elif length+1 == n:
            return '[ZZZ] %s' % line

        # Does not spark joy - cases where the `n` is bigger than the C-string length
        # it's not a bug per se (i.e. won't accept bad inputs) but a programming/typo error
        # Example:
        #   strncmp(power->bat_type, "li", 30)  - the n=30 is hilarious
        elif length != n:
            return '[YYY] %s   strlen=%d, n=%d' % (line, length, n)

        # Valid case - spammy one but useful for debugging
        else:
            return '[OK] %s   strlen=%d, n=%d : arg1=%r, arg2=%r' % (line, length, n, arg1, arg2)

"""
Commands to run:

P=$(basename `pwd`)
RESULTS_PATH="../${P}_results"
mkdir "$RESULTS_PATH"

git grep -i 'strncmp[ ]?[(].*[)]' > "$RESULTS_PATH/strncmp"
git grep -i 'strnicmp[ ]?[(].*[)]' > "$RESULTS_PATH/strnicmp"
git grep -i 'strncat[ ]?[(].*[)]' > "$RESULTS_PATH/strncat"
git grep -i 'strncpy[ ]?[(].*[)]' > "$RESULTS_PATH/strncpy"
git grep -i 'memcmp[ ]?[(].*[)]' > "$RESULTS_PATH/memcmp"
git grep -i 'strncasecmp[ ]?[(].*[)]' > "$RESULTS_PATH/strncasecmp"
"""

def maybe_grep(string, results_out_path, force_grep=False):
    joiner = lambda s: os.path.join(results_out_path, s)
    
    cmd = "grep --exclude-dir=.git -R -i '%s[ ]*[(].*[)]' . > %s" % (string, joiner(string))
    print('Executing', cmd)
    os.system(cmd)
    """
    git grep -i 'strnicmp[ ]?[(].*[)]' > "$RESULTS_PATH/strnicmp"
    git grep -i 'strncat[ ]?[(].*[)]' > "$RESULTS_PATH/strncat"
    git grep -i 'strncpy[ ]?[(].*[)]' > "$RESULTS_PATH/strncpy"
    git grep -i 'memcmp[ ]?[(].*[)]' > "$RESULTS_PATH/memcmp"
    git grep -i 'strncasecmp[ ]?[(].*[)]' > "$RESULTS_PATH/strncasecmp"
    """

check_all = (
    'strncmp',
    'strnicmp',
    'strncat',
    'strncpy',
    'memcmp',
    'strncasecmp',
    'stpncpy',
    'strncpy'
)

#line = './xen/include/acpi/acmacros.h:#define acpi_compare_name(a,b)          (!acpi_strncmp (acpi_cast_ptr (char,(a)), acpi_cast_ptr (char,(b)), acpi_name_size))'
#debug_line(line, prefix='strncmp')

def single_file():
    import sys
    inp = sys.stdin.read()
    for c in check_all:
        findme(prefix=c, string=inp)

if __name__ == '__main__':
    single_file()
    exit()
    import sys
    
    results_out_path, force_grep = sys.argv[1], '--force' in sys.argv

    if results_out_path == '.':
        results_out_path = os.getcwd() + "_results"

    print('[!] Results path = %r' % results_out_path)

    if os.path.exists(results_out_path) and not force_grep:
        print("[!] Results path exists, skipping grepping the project (pass `--force` to re-grep)")
    else:
        try:
            os.makedirs(results_out_path)
        except FileExistsError:
            pass
        for c in check_all:
            print("Grepping for %s..." % c)
            maybe_grep(c, results_out_path, force_grep)

    for c in check_all:
        p = os.path.join(results_out_path, c)
        findme(prefix=c, string=open(p).read())

