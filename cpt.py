#!/usr/bin/python3
"""Naman's tool to download and set-up problems using Competitive Companion
Usage:
  cpt.py
  cpt.py t
  cpt.py --test
  cpt.py e
  cpt.py --echo
  cpt.py g
  cpt.py --gen

Options:
  -h --help  Show this screen
  e --echo  Just echo received responses and exit
  t --test  Test your code against the downloaded/custom testcases
  g --gen  Generate code file with preset template
"""

from docopt import docopt
import sys
import os
import http.server
import json
from pathlib import Path
import subprocess
import re
import shutil
from pathlib import Path
import filecmp
from colorama import Fore, Style

def listen_once(*, timeout=None):
	json_data = None

	class CompetitiveCompanionHandler(http.server.BaseHTTPRequestHandler):
		def do_POST(self):
			nonlocal json_data
			json_data = json.load(self.rfile)

	with http.server.HTTPServer(('127.0.0.1', 1327), CompetitiveCompanionHandler) as server:
		server.timeout = timeout
		server.handle_request()

	return json_data

def listen_many(*, num_items=None, num_batches=None, timeout=None):
    if num_items is not None:
        res = []
        for _ in range(num_items):
            cur = listen_once(timeout=None)
            res.append(cur)
        return res

    if num_batches is not None:
        res = []

        batches = {}
        while len(batches) < num_batches or any(need for need, tot in batches.values()):
            print(f"Waiting for {num_batches} batches:", batches)
            cur = listen_once(timeout=None)
            res.append(cur)

            cur_batch = cur['batch']
            batch_id = cur_batch['id']
            batch_cnt = cur_batch['size']
            if batch_id not in batches:
                batches[batch_id] = [batch_cnt, batch_cnt]
            assert batches[batch_id][0] > 0
            batches[batch_id][0] -= 1

        return res

    res = [listen_once(timeout=None)]
    while True:
        cnd = listen_once(timeout=timeout)
        if cnd is None:
            break
        res.append(cnd)
    return res


base_path = Path.home().joinpath('codex', 'cptool')
contest_path = base_path.joinpath('contests')
template_file_path = base_path.joinpath('template.cpp')


def gen():
	cwd = Path.cwd()
	code_file_name = cwd.joinpath('code.cpp')

	if code_file_name.is_file():
		print('code.cpp already exists. Do you want to overwrite it with preset template?\nPlease enter y/n:')
		choice = input()
		if choice != 'y':
			return

	template_file = open(template_file_path, 'r')
	to_write = template_file.read()
	template_file.close()
	code_file = open(code_file_name , 'w')
	code_file.write(to_write)
	code_file.close()


def test():
	cwd = Path.cwd()
	io_file_number = 0
	extension = '.txt'

	# while True:
	# 	output_file_name = cwd.joinpath('out' + str(io_file_number) + extension)
	# 	if(os.path.isfile(output_file_name)):
	# 		os.remove(output_file_name)
	# 		io_file_number += 1
	# 	else:
	# 		break

	executable_file_name = cwd.joinpath('code')
	if os.path.isfile(executable_file_name):
		os.remove(executable_file_name)
	cmd = 'g++ -Dnaman1601 -std=c++17 -Wall -Wextra -Wshadow -D_GLIBCXX_DEBUG -ggdb3 -fsanitize=address -fsanitize=undefined code.cpp -o code'
	os.system(cmd)
	if not os.path.isfile(executable_file_name):
		print(Fore.RED + 'COMPILATION ERROR' + Style.RESET_ALL)
		return

	io_file_number = 0
	
	while True:
		input_file_name = cwd.joinpath('in' + str(io_file_number) + extension)
		output_file_name = cwd.joinpath('out' + str(io_file_number) + extension)
		if os.path.isfile(input_file_name):
			os.system(str(executable_file_name) + ' < ' + str(input_file_name) + ' > ' + str(output_file_name))
			io_file_number += 1
		else:
			break
	
	for idx in range(io_file_number):
		input_file_name = cwd.joinpath('in' + str(idx) + extension)
		answer_file_name = cwd.joinpath('ans' + str(idx) + extension)
		output_file_name = cwd.joinpath('out' + str(idx) + extension)

		output_file_content = open(output_file_name).read().strip()
		answer_file_content = open(answer_file_name).read().strip()

		if(output_file_content == answer_file_content):
			print(Fore.GREEN + 'Passed testcase #' + str(idx))
			print(Style.RESET_ALL)
		else:
			print(Fore.RED + 'WA on testcase #' + str(idx), end = '')
			print(Style.RESET_ALL)
			print(Fore.CYAN + 'Input:\n' + Style.RESET_ALL + open(input_file_name).read())
			print(Fore.CYAN + 'Expected answer:\n' + Style.RESET_ALL + answer_file_content)
			print(Fore.CYAN + '\nYour output:\n' + Style.RESET_ALL + output_file_content)



def get_contest_id(url):
	find_list = ['codeforces.com/contest/', 'atcoder.jp/contests/', 'codeforces.com/problemset/problem/', 'codechef.com/']
	to_find = ''

	for option in find_list:
		if option in url:
			to_find = option
			break
	
	idx = url.index(to_find) + len(to_find)
	retval = ''

	while url[idx] != '/':
		retval += url[idx]
		idx += 1
	
	return retval.lower()
		

def make_problem(json_data):
	oj_name = ''

	if json_data['group'].startswith('Codeforces'):
		oj_name = 'codeforces'
	elif json_data['group'].startswith('AtCoder'):
		oj_name = 'atcoder'
	elif json_data['group'].startswith('CodeChef'):
		oj_name = 'codechef'

	problem_name = json_data['name'][0].lower()

	if(json_data['name'][1].isdigit()):
		problem_name += str(json_data['name'][1])

	if oj_name == 'codechef':
		problem_name = json_data['url'][json_data['url'].rindex('/') + 1:].lower()

	contest_id = get_contest_id(json_data['url'])
	target_path = contest_path.joinpath(oj_name, contest_id, problem_name)
	file_name = 'code.cpp'
	file_path = target_path.joinpath(file_name)

	make_new_code_file = True

	if(os.path.isdir(target_path)):
		print('The problem already exists! Re-parsing testcase files.')
		make_new_code_file = False
	
	if make_new_code_file:
		os.makedirs(target_path)
		template_file = open(template_file_path, 'r')
		to_write = template_file.read()
		template_file.close()
		to_write = '// time limit: ' + str( json_data['timeLimit']) + 's\n' + to_write
		to_write = '// memory limit: ' + str(json_data['memoryLimit']) + 'MB\n' + to_write
		to_write = '// url: ' + json_data['url'] + '\n' + to_write
		code_file = open(file_path , 'w')
		code_file.write(to_write)
		code_file.close()

	io_file_number = 0
	extension = '.txt'

	for testcase in json_data['tests']:
		input_file_name = target_path.joinpath('in' + str(io_file_number) + extension)
		answer_file_name = target_path.joinpath('ans' + str(io_file_number) + extension)
		io_file_number += 1
		input_file = open(input_file_name, 'w')
		input_file.write(testcase['input'])
		input_file.close()
		answer_file = open(answer_file_name, 'w')
		answer_file.write(testcase['output'])
		answer_file.close()
	
	print('Problem successfully made in directory:\n' + 'cd ' + str(target_path))
	os.system('subl ' + str(file_path))


def main():
	args = docopt(__doc__)

	if args['e'] or args['--echo']:
		datas = listen_many(num_batches = 1)
		for data in datas:
			print(data)
		return
	
	if args['t'] or args['--test']:
		test()
		return

	if args['g'] or args['--gen']:
		gen()
		return

	os.chdir(base_path)
	datas = listen_many(num_batches = 1)
	for json_data in datas:
		make_problem(json_data)


if __name__ == '__main__':
	main()