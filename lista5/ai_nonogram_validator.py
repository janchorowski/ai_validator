#!/pio/os/anaconda/bin/python
# -*- coding: UTF-8 -*-
'''
Prosta sprawdzarka. Przykłady użycia:

1. Uruchomienie wszystkich testów dla danego zadania:
  `python validator.py zad1 python rozwiazanie.py`

2. Uruchomienie wybranych testów
  `python validator.py --cases 1,3-5 zad1 a.out`

3. Urochomienie na innych testach
  `python validator.py --testset large_tests.yaml zad1 python rozwiazanie.py`

4. Wypisanie przykładowego wejścia/wyjścia:
  `python validator.py --show_example zad1`

5. Wypisanie informacji o rozwiązaniu:
  `python validator.py --verbose zad1 python rozwiazanie.py`

6. Wymuszenie użycia STDIN/STDOUT do komunikacji:
  `python validator.py --stdio zad1 python rozwiazanie.py`

7. Ustawienie mnożnika dla limitów czasowych:
  `python validator.py --timeout-multiplier 2.5 zad1 python rozwiazanie.py`


'''

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import os
import signal
import subprocess
import sys
import threading
import time

import numpy as np

import yaml

DEFAULT_TESTSET_YAML = u'''
zad1: {}
'''
DEFAULT_TESTSET = yaml.load(DEFAULT_TESTSET_YAML)
AI_SU = "/pio/scratch/2/ai_solutions/ai_su"
SKILL = "/pio/scratch/2/ai_solutions/skill"


VERBOSE = False

# Comparison functions

class ValidatorException(Exception):
    pass


def fail(message):
    raise ValidatorException(message)


def compare(returned, expected, message="Contents"):
    if returned != expected:
        fail('%s differ. Got: "%s", expceted: "%s"' % (
             message, returned, expected))


def whitespace_relaxed_validator(case, process_out):
    """
    Compare two strings ignoring whitespaces and trailing newlines.
    """
    ref_out = whitespace_normalize(case['out'])
    process_out = whitespace_normalize(process_out)
    return compare(process_out, ref_out, "Outputs")


def perlines_validator(case, process_out, line_compare_fun=compare):
    """
    Compare two strings line by line, ignoring whitespaces.
    """
    ref_lines = whitespace_normalize(case['out']).split('\n')
    process_lines = whitespace_normalize(process_out).split('\n')
    compare(len(process_lines), len(ref_lines), "Number of lines")
    for lnum, (proc_line, ref_line) in enumerate(
            zip(process_lines, ref_lines)):
        line_compare_fun(proc_line, ref_line, "Line %d contents" % (lnum + 1,))


def count_blocks(r):
    b = 0
    ret = []
    for e in r:
        if e == 0:
            if b > 0:
                ret.append(b)
                b = 0
        else:
            b += 1
    if b > 0:
        ret.append(b)
    # according to the following clarification, an empty row/column 
    # should be represented in input as a single zero
    # https://skos.ii.uni.wroc.pl/mod/forum/discuss.php?d=387
    if ret == []:
        ret = [0]
    return ret


def nonogram_validator(case, process_out):
    case_def = [[int(i) for i in l.split()]
                for l in case['inp'].split('\n') if l.strip()]
    img = [[0 if c=='.' else 1 for c in l.strip()]
           for l in process_out.split('\n') if l.strip()]
    img = np.array(img)

    if img.shape != tuple(case_def[0]):
        fail("Wrong output shape.")
    ret_def = (
        [[img.shape[0], img.shape[1]]] +
        [count_blocks(r) for r in img] +
        [count_blocks(r) for r in img.T])
    if case_def != ret_def:
        fail("Solution does not match spec.")


# Comparison function utils
def ensure_unicode(obj):
    if sys.version_info[0] == 3:
        if isinstance(obj, str):
            return obj
        elif isinstance(obj, bytes):
            return obj.decode('utf8')
        else:
            return str(obj)
    else:
        if isinstance(obj, unicode):
            return obj
        elif isinstance(obj, str):
            return obj.decode('utf8')
        else:
            return unicode(obj)
    return obj


def whitespace_normalize(obj):
    """
    Optionally convert to string and normalize newline and space characters.
    """
    string = ensure_unicode(obj)
    lines = string.replace('\r', '').strip().split('\n')
    lines = [' '.join(l.strip().split()) for l in lines]
    return '\n'.join(lines)


# Subprocess handling utils
try:  # py3
    from shlex import quote as shellquote
except ImportError:  # py2
    from pipes import quote as shellquote


if os.name == 'nt':
    def shellquote(arg):
        return subprocess.list2cmdline([arg])

    def kill_proc(process):
        if process.poll() is None:
            print('Killing subprocess.')
            subprocess.call(['taskkill', '/F', '/T', '/PID', str(process.pid)])
else:
    def killcg(cgroup):
        with open(os.path.join('/sys/fs/cgroup/cpuset',
                               cgroup, 'cgroup.procs')) as f:
            for line in f:
                subprocess.call([SKILL, '-TERM', '--', line.strip()])
                subprocess.call([SKILL, '-KILL', '--', line.strip()])

    def kill_proc(process):
        if process.poll() is None:
            print('Killing subprocess.')
            with open(os.path.join('/proc', str(process.pid), 'cgroup')) as f:
                for line in f:
                    if 'cpuset' in line:
                        cgroup = line.strip().split('/')[-1]
                        if cgroup.startswith('ai'):
                            killcg(cgroup)
                            if process.poll() is not None:
                                return
            try:
                pgid = os.getpgid(process.pid)
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except:
                    subprocess.call([SKILL, '-TERM', '--', str(-pgid)])
                    subprocess.call([SKILL, '-KILL', '--', str(-pgid)])
            except:
                pid = process.pid
                try:
                    os.kill(pid, signal.SIGTERM)
                except:
                    subprocess.call([SKILL, '-TERM', '--', str(pid)])
                    subprocess.call([SKILL, '-KILL', '--', str(pid)])


def run_and_score_case(program, defaults, case_def, validator, timeout_multiplier):
    opts = dict(defaults)
    opts.update(case_def)
    opts['timeout'] *= timeout_multiplier
    process_out, elapsed_time = run_case(program, **opts)
    if VERBOSE:
        print("Got output:")
        print(process_out)
    measurements = validator(opts, process_out)
    measurements = measurements or {}
    measurements['time'] = elapsed_time
    return measurements


def run_case(program, inp, out=None,
             input_file='<stdin>', output_file='<stdout>',
             timeout=1.0):
    del out  # unused
    inp = ensure_unicode(inp)
    if inp[-1] != '\n':
        inp += '\n'
    inp = inp.encode('utf8')

    if input_file != '<stdin>':
        with open(input_file, 'wb') as in_f:
            in_f.write(inp)
        inp = None
    try:
        if output_file != '<stdout>':
            os.remove(output_file)
    except:
        pass

    stdin = subprocess.PIPE if input_file == '<stdin>' else None
    stdout = subprocess.PIPE if output_file == '<stdout>' else None
    process_out = ''
    process = None

    try:
        if os.name == 'nt':
            kwargs = {}
        else:
            kwargs = {'preexec_fn': os.setpgrp}

        process = subprocess.Popen(
            program, shell=True, stdin=stdin, stdout=stdout, **kwargs)
        start = time.time()
        if timeout > 0:
            timer = threading.Timer(timeout, kill_proc, [process])
            timer.start()

        process_out, _ = process.communicate(inp)
        elapsed = time.time() - start
    except Exception as e:
        fail(str(e))
    finally:
        if process:
            kill_proc(process)
        if timeout > 0:
            timer.cancel()
    if process.poll() != 0:
        fail("Bad process exit status: %d" % (process.poll(),))

    if output_file != '<stdout>':
        if not os.path.isfile(output_file):
            fail("Output file %s does not exist" % (output_file, ))
        with open(output_file, 'rb') as out_f:
            process_out = out_f.read()
    process_out = process_out.decode('utf8')

    return process_out, elapsed


def ensure_newline_string(obj):
    obj = ensure_unicode(obj)
    if obj[-1] != '\n':
        obj += '\n'
    return obj


def show_example(defaults, case_def):
    opts = dict(defaults)
    opts.update(case_def)
    print("Input is passed using %s and contains:" % (opts['input_file'],))
    print(ensure_newline_string(opts["inp"]))
    print("Output is expected in %s with contents:" % (opts['output_file'],))
    print(ensure_newline_string(opts["out"]))


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--cases', default='',
        help='Comma-separated list of test cases to run, e.g. 1,2,3-6.')
    parser.add_argument(
        '--testset', default='/pio/scratch/2/ai_solutions/quick_nonograms_tests.yaml',
        help='Path to a YAML test set definition.')
    parser.add_argument(
        '--show_example', default=False, action='store_true',
        help='Print a sample input/output pair.')
    parser.add_argument(
        '--timeout-multiplier', '-tm',
        help='Multiply timeout by provided amount, e.g. 2.13')
    parser.add_argument(
        '--verbose', default=False, action='store_true',
        help='Print more information about solutions.')
    parser.add_argument(
        '--stdio', default=False, action='store_true',
        help='Use stdin/stdout for communication.')
    parser.add_argument(
        '--problem', default='zad1',
        help='Problem form this homework, one of: %s.' %
        (', '.join(sorted(DEFAULT_TESTSET.keys())),))
    parser.add_argument(
        '--cgroup', default='',
        help='cgroup for ai_su')
    parser.add_argument("--results", default='')
    parser.add_argument(
        'program_dir',
        help='Program dir to execute, e.g. obrazki_jch.')
    return parser


def get_program(program_dir, cgroup):
    if cgroup:
        if open(os.path.join('/sys/fs/cgroup/cpuset', cgroup, 'tasks')
                    ).read().strip() != '':
                sys.stderr.write(
                    'There are tasks in the selected cgroups!\n')
                sys.exit(1)
        cgroup = '--cgroup %s' % (cgroup,)
    return 'exec %s %s %s' % (AI_SU, cgroup, program_dir)
    #return ' '.join([shellquote(a) for a in args])


def get_cases(problem_def, cases):
    problem_cases = problem_def['cases']
    if cases == '':
        for case in enumerate(problem_cases, 1):
            yield case
        return
    cases = cases.strip().split(',')
    for case in cases:
        if '-' not in case:
            case = int(case) - 1
            if case < 0:
                raise Exception('Bad case number: %d' % (case + 1,))
            yield case + 1, problem_cases[case]
        else:
            low, high = case.split('-')
            low = int(low) - 1
            high = int(high)
            if low < 0 or high > len(problem_cases):
                raise Exception('Bad case range: %s' % (case,))
            for case in range(low, high):
                yield case + 1, problem_cases[case]


if __name__ == '__main__':
    parser = get_argparser()
    args = parser.parse_args()
    VERBOSE = args.verbose

    with open(args.testset) as testset_f:
        testset = yaml.load(testset_f)
    if args.problem not in testset:
        print('Problem not known: %s. Choose one of %s.' %
              (args.problem, ', '.join(sorted(testset.keys()))))

    problem_def = testset[args.problem]
    problem_validator = eval(problem_def['validator'])
    problem_cases = get_cases(problem_def, args.cases)
    program = get_program(args.program_dir, args.cgroup)

    if args.show_example:
        show_example(problem_def['defaults'], next(problem_cases)[1])
        sys.exit()

    failed_cases = []
    ok_cases = []
    t_start = time.time()
    for case_num, case_def in problem_cases:
        print('Running case %d... ' % (case_num,), end='')
        try:
            timeout_multiplier = float(args.timeout_multiplier) if args.timeout_multiplier and float(args.timeout_multiplier) > 1 else 1
            if args.stdio:
                case_def['input_file'] = '<stdin>'
                case_def['output_file'] = '<stdout>'
            case_meas = run_and_score_case(
                program, problem_def['defaults'], case_def,
                problem_validator, timeout_multiplier)
            ok_cases.append((case_num, case_meas))
            print('OK!')
        except ValidatorException as e:
            failed_cases.append(case_num)
            print('Failed:')
            print(str(e))
        sys.stdout.flush()
    tot_time = time.time() - t_start
    print('\nValidation result: %d/%d cases pass. Eval time: %f\n' % (
        len(ok_cases), len(ok_cases) + len(failed_cases), tot_time))

    tot_meas = {}
    for nc, meas in ok_cases:
        for k, v in meas.items():
            tot_meas[k] = tot_meas.get(k, 0) + v
    for k, v in tot_meas.items():
        print("For passing cases total %s: %s" % (k, v))

    if args.results:
        with open(args.results, 'a') as rf:
            rf.write('%s, %d, %f, %f\n' %
                     (os.path.basename(args.program_dir),
                      len(ok_cases), tot_meas.get('time', -1), tot_time))

    if failed_cases:
        print('\nSome test cases have failed. '
              'To rerun the failing cases execute:')
        misc_opts = ''
        if args.verbose:
            misc_opts = ' --verbose'
        if args.timeout_multiplier:
            misc_opts += ' --timeout-multiplier ' + args.timeout_multiplier
        if args.testset:
            misc_opts = '%s --testset %s' % (
                misc_opts, shellquote(args.testset),)
        cases_opt = '--cases ' + ','.join([str(fc) for fc in failed_cases])
        print('python validator.py%s %s %s %s' %
              (misc_opts, cases_opt, args.problem, program))

