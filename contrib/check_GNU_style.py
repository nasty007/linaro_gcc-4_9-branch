#!/usr/bin/env python3
#
# Checks some of the GNU style formatting rules in a set of patches.
# The script is a rewritten of the same bash script and should eventually
# replace the former script.
#
# This file is part of GCC.
#
# GCC is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 3, or (at your option) any later
# version.
#
# GCC is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with GCC; see the file COPYING3.  If not see
# <http://www.gnu.org/licenses/>.  */
#
# The script requires python packages, which can be installed via pip3
# like this:
# $ pip3 install unidiff termcolor 

import sys
import re
import argparse
import unittest

try:
    from termcolor import colored
except ImportError:
    print('termcolor module is missing (run: pip3 install termcolor)')
    exit(3)

try:
    from unidiff import PatchSet
except ImportError:
    print('unidiff module is missing (run: pip3 install unidiff)')
    exit(3)

from itertools import *

ws_char = '█'
ts = 8

def error_string(s):
    return colored(s, 'red', attrs = ['bold'])

class CheckError:
    def __init__(self, filename, lineno, console_error, error_message,
        column = -1):
        self.filename = filename
        self.lineno = lineno
        self.console_error = console_error
        self.error_message = error_message
        self.column = column

    def error_location(self):
        return '%s:%d:%d:' % (self.filename, self.lineno,
            self.column if self.column != -1 else -1)

class LineLengthCheck:
    def __init__(self):
        self.limit = 80
        self.expanded_tab = ' ' * ts

    def check(self, filename, lineno, line):
        line_expanded = line.replace('\t', self.expanded_tab)
        if len(line_expanded) > self.limit:
            return CheckError(filename, lineno,
                line_expanded[:self.limit]
                    + error_string(line_expanded[self.limit:]),
                'lines should not exceed 80 characters', self.limit)

        return None

class SpacesCheck:
    def __init__(self):
        self.expanded_tab = ' ' * ts

    def check(self, filename, lineno, line):
        i = line.find(self.expanded_tab)
        if i != -1:
            return CheckError(filename, lineno,
                line.replace(self.expanded_tab, error_string(ws_char * ts)),
                'blocks of 8 spaces should be replaced with tabs', i)

class TrailingWhitespaceCheck:
    def __init__(self):
        self.re = re.compile('(\s+)$')

    def check(self, filename, lineno, line):
        m = self.re.search(line)
        if m != None:
            return CheckError(filename, lineno,
                line[:m.start(1)] + error_string(ws_char * len(m.group(1)))
                + line[m.end(1):],
                'trailing whitespace', m.start(1))

class SentenceSeparatorCheck:
    def __init__(self):
        self.re = re.compile('\w\.(\s|\s{3,})\w')

    def check(self, filename, lineno, line):
        m = self.re.search(line)
        if m != None:
            return CheckError(filename, lineno,
                line[:m.start(1)] + error_string(ws_char * len(m.group(1)))
                + line[m.end(1):],
                'dot, space, space, new sentence', m.start(1))

class SentenceEndOfCommentCheck:
    def __init__(self):
        self.re = re.compile('\w\.(\s{0,1}|\s{3,})\*/')

    def check(self, filename, lineno, line):
        m = self.re.search(line)
        if m != None:
            return CheckError(filename, lineno,
                line[:m.start(1)] + error_string(ws_char * len(m.group(1)))
                + line[m.end(1):],
                'dot, space, space, end of comment', m.start(1))

class SentenceDotEndCheck:
    def __init__(self):
        self.re = re.compile('\w(\s*\*/)')

    def check(self, filename, lineno, line):
        m = self.re.search(line)
        if m != None:
            return CheckError(filename, lineno,
                line[:m.start(1)] + error_string(m.group(1)) + line[m.end(1):],
                'dot, space, space, end of comment', m.start(1))

class FunctionParenthesisCheck:
    # TODO: filter out GTY stuff
    def __init__(self):
        self.re = re.compile('\w(\s{2,})?(\()')

    def check(self, filename, lineno, line):
        if '#define' in line:
            return None

        m = self.re.search(line)
        if m != None:
            return CheckError(filename, lineno,
                line[:m.start(2)] + error_string(m.group(2)) + line[m.end(2):],
                'there should be exactly one space between function name ' \
                'and parenthesis', m.start(2))

class SquareBracketCheck:
    def __init__(self):
        self.re = re.compile('\w\s+(\[)')

    def check(self, filename, lineno, line):
        m = self.re.search(line)
        if m != None:
            return CheckError(filename, lineno,
                line[:m.start(1)] + error_string(m.group(1)) + line[m.end(1):],
                'there should be no space before a left square bracket',
                m.start(1))

class ClosingParenthesisCheck:
    def __init__(self):
        self.re = re.compile('\S\s+(\))')

    def check(self, filename, lineno, line):
        m = self.re.search(line)
        if m != None:
            return CheckError(filename, lineno,
                line[:m.start(1)] + error_string(m.group(1)) + line[m.end(1):],
                'there should be no space before closing parenthesis',
                m.start(1))

class BracesOnSeparateLineCheck:
    # This will give false positives for C99 compound literals.

    def __init__(self):
        self.re = re.compile('(\)|else)\s*({)')

    def check(self, filename, lineno, line):
        m = self.re.search(line)
        if m != None:
            return CheckError(filename, lineno,
                line[:m.start(2)] + error_string(m.group(2)) + line[m.end(2):],
                'braces should be on a separate line', m.start(2))

class TrailinigOperatorCheck:
    def __init__(self):
        regex = '^\s.*(([^a-zA-Z_]\*)|([-%<=&|^?])|([^*]/)|([^:][+]))$'
        self.re = re.compile(regex)

    def check(self, filename, lineno, line):
        m = self.re.search(line)
        if m != None:
            return CheckError(filename, lineno,
                line[:m.start(1)] + error_string(m.group(1)) + line[m.end(1):],
                'trailing operator', m.start(1))

class LineLengthTest(unittest.TestCase):
    def setUp(self):
        self.check = LineLengthCheck()

    def test_line_length_check_basic(self):
        r = self.check.check('foo', 123, self.check.limit * 'a' + ' = 123;')
        self.assertIsNotNone(r)
        self.assertEqual('foo', r.filename)
        self.assertEqual(80, r.column)
        self.assertEqual(r.console_error,
            self.check.limit * 'a' + error_string(' = 123;'))

def main():
    parser = argparse.ArgumentParser(description='Check GNU coding style.')
    parser.add_argument('file', help = 'File with a patch')
    parser.add_argument('-f', '--format', default = 'stdio',
        help = 'Display format',
        choices = ['stdio', 'quickfix'])
    args = parser.parse_args()

    checks = [LineLengthCheck(), SpacesCheck(), TrailingWhitespaceCheck(),
        SentenceSeparatorCheck(), SentenceEndOfCommentCheck(),
        SentenceDotEndCheck(), FunctionParenthesisCheck(),
        SquareBracketCheck(), ClosingParenthesisCheck(),
        BracesOnSeparateLineCheck(), TrailinigOperatorCheck()]
    errors = []

    with open(args.file, 'rb') as diff_file:
        patch = PatchSet(diff_file, encoding = 'utf-8')

    for pfile in patch.added_files + patch.modified_files:
        t = pfile.target_file.lstrip('b/')
        # Skip testsuite files
        if 'testsuite' in t:
            continue

        for hunk in pfile:
            delta = 0
            for line in hunk:
                if line.is_added and line.target_line_no != None:
                    for check in checks:
                        e = check.check(t, line.target_line_no, line.value)
                        if e != None:
                            errors.append(e)

    if args.format == 'stdio':
        fn = lambda x: x.error_message
        i = 1
        for (k, errors) in groupby(sorted(errors, key = fn), fn):
            errors = list(errors)
            print('=== ERROR type #%d: %s (%d error(s)) ==='
                % (i, k, len(errors)))
            i += 1
            for e in errors:
                print(e.error_location () + e.console_error)
            print()

        exit(0 if len(errors) == 0 else 1)
    elif args.format == 'quickfix':
        f = 'errors.err'
        with open(f, 'w+') as qf:
            for e in errors:
                qf.write('%s%s\n' % (e.error_location(), e.error_message))
        if len(errors) == 0:
            exit(0)
        else:
            print('%d error(s) written to %s file.' % (len(errors), f))
            exit(1)
    else:
        assert False

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main()
    else:
        unittest.main()
