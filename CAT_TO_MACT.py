# MARCDRED'S CAT_TO_MACT.py V4.1 #
# marcdred@outlook.com #
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
	from typing_extensions import Self
import struct
from dataclasses import dataclass
import math
import numpy
from itertools import chain
import os
import sys


## SETTINGS ##
bool_little_endian = 1
bool_skip_id_zero = 1
bool_guess_param_types = 1
bool_generate_mact = 0
bool_generate_templates = 0
bool_write_debug = 0
bool_print_debug = 1
number_of_param_digits = 5


@dataclass
class DbLogic:
	title: str
	params: list[DbParam]


@dataclass
class DbParam:
	id: int
	title: str
	type: str


@dataclass
class HashHelper:
	title: str
	hashes: list[str]


@dataclass
class StringHelper:
	offset: int
	string: str


@dataclass
class ParamVariableString:
	string_offset: int
	number_of_variables: int
	variable_offsets: list[int]


@dataclass
class ParamVariableGroup:
	group_offset: int
	number_of_variables: int
	variable_offsets: list[int]


@dataclass
class VariableConditionGroup:
	offset: int
	condition_offsets: list[int]


@dataclass
class Param:
	logic_helper: LogicHelper
	offset: int
	id: int
	type: str
	value: bytes


@dataclass
class LogicHelper:
	nodes: list[CatNode]
	offset: int
	hash: int
	opti_offset: int
	params: list[Params]


@dataclass
class CatNode:
	offset: int
	type: int
	hash: int
	file_offset: str
	path_offset: str
	condition_offsets: list[int]
	track_offsets: list[int]
	children: list[Self]


def format_read(file, format):
	global bool_little_endian
	if bool_little_endian == 1:
		format = "<"+format
	else:
		format = ">"+format
	size = struct.calcsize(format)
	data = file.read(size)
	value = struct.unpack(format, data)
	if len(value) == 1:
		value = value[0]
	return value


def get_bits(data, start, end):
	bit_size = len(str(bin(data))[2:])
	# print(str(bin(data)))
	mask = int((bit_size - end) * "0" + end * "1", 2)
	data = data & mask
	data = data >> start
	return data


def signal(bit):
	if bit:
		return -1
	else:
		return 1


def read_string(file):
	bool_end = 0
	string = ""
	while not bool_end:
		c = file.read(1)
		if not c or c == b'\x00':
			bool_end = 1
			break
		string = string+c.decode('utf-8')
	return string


def pretty_bytes(value):
		if value is None:
			return "NULL"
		if(isinstance(value, int)):
			value = value.to_bytes(4, byteorder='little')
		string = value.hex()
		string = string.upper()
		if not string:
			string = "NULL"
		string = "0x" + string
		return string


def split_string_removing(string, pos):
		return string[:pos], string[pos+1:]


def get_keywords_from_line(line):
	# get split positions, don't split quoted characters
	quoting = False
	split_at = []
	for i, c in enumerate(line):
		if not quoting:
			if c.isspace():
				split_at.append(i)
		if c == "\"":
			quoting = not quoting
	# make split
	keywords = []
	start = 0
	for split in split_at:
		keyword = line[start:split]
		keywords.append(keyword)
		start = split+1
	keywords.append(line[start:len(line)])
	# remove empty words
	keywords = list(keywords)
	non_empty_keywords = []
	for kw in keywords:
		if len(kw):
			non_empty_keywords.append(kw)
	return non_empty_keywords


# hash db management
bool_has_db_hashes = False
bool_has_db_hashes_titles = False
bool_has_db_hashes_generic = False
# logic db management
bool_has_db_tracks = False
bool_has_db_conditions = False

## READ DB HASHES ##
def read_db_hashes(file, db):
	hash_lines = file.readlines()
	for l in hash_lines:
		kws = get_keywords_from_line(l)
		title = kws[0]
		hashes = [h.upper() for h in kws[1:]]
		hh = HashHelper(title, hashes)
		db.append(hh)
db_hashes = []
db_hashes_titles = []
db_hashes_generic = []
fn_track_hashes = "DB"+os.sep+"HASHES_TRACKS.txt"
fn_condition_hashes = "DB"+os.sep+"HASHES_CONDITIONS.txt"
fn_title_hashes = "DB"+os.sep+"HASHES_TITLES.txt"
fn_generic_hashes = "DB"+os.sep+"HASHES_GENERIC.txt"
if os.path.exists(fn_track_hashes):
	track_hashes = open(fn_track_hashes, "r")
	read_db_hashes(track_hashes, db_hashes)
	track_hashes.close()
	bool_has_db_hashes = True
else:
	print("Warning: No '{0}' found.".format(fn_track_hashes))
if os.path.exists(fn_condition_hashes):
	condition_hashes = open(fn_condition_hashes, "r")
	read_db_hashes(condition_hashes, db_hashes)
	condition_hashes.close()
	bool_has_db_hashes = True
else:
	print("Warning: No '{0}' found.".format(fn_condition_hashes))
if os.path.exists(fn_title_hashes):
	title_hashes = open(fn_title_hashes, "r")
	read_db_hashes(title_hashes, db_hashes_titles)
	title_hashes.close()
	bool_has_db_hashes_titles = True
else:
	print("Warning: No '{0}' found.".format(fn_title_hashes))
if os.path.exists(fn_generic_hashes):
	generic_hashes = open(fn_generic_hashes, "r")
	read_db_hashes(generic_hashes, db_hashes_generic)
	generic_hashes.close()
	bool_has_db_hashes_generic = True
else:
	print("Warning: No '{0}' found.".format(fn_generic_hashes))

def read_db_logics(file):
	db_logics = []
	lines = file.readlines()
	last_logic = None
	for l in lines:
		my_line = l.split()
		if len(my_line)==0 or l[0] == '#':
			continue
		if l[0] != "\t":
			if last_logic is not None:
				db_logics.append(last_logic)
			logic = DbLogic(my_line[0], [])
			last_logic = logic
		else:
			p = DbParam(my_line[0], my_line[1], my_line[2])
			last_logic.params.append(p)
	if last_logic is not None:
		db_logics.append(last_logic)
	return db_logics


# WARNING: track db and condition db must be kept separate
# because there are nodes that share the same name (both track/condition)
## READ TEMPLATES ##
db_tracks = []
db_conditions = []
fn_dbt = "TEMPLATES"+os.sep+"TEMPLATES_TRACKS.txt"
fn_dbc = "TEMPLATES"+os.sep+"TEMPLATES_CONDITIONS.txt"
if os.path.exists(fn_dbt):
	file_dbt = open(fn_dbt, "r")
	db_tracks = read_db_logics(file_dbt)
	file_dbt.close()
	bool_has_db_tracks = True
else:
	print("Warning: No '{0}' found.".format(fn_dbt))
if os.path.exists(fn_dbc):
	file_dtc = open(fn_dbc, "r")
	db_conditions = read_db_logics(file_dtc)
	file_dtc.close()
	bool_has_db_conditions = True
else:
	print("Warning: No '{0}' found.".format(fn_dbc))


# Get MODE and 
# get CAT files from sys.argv if MODE is regular CAT_TO_MACT,
# get CAT path from sys.argv if MODE is GENERATE_TEMPLATES.
my_cat_files = []
cat_path = None
sys_argv = sys.argv[1:]
for i, arg in enumerate(sys_argv):
	if sys_argv[i].upper() == "--GENERATE-TEMPLATES":
		bool_generate_mact = 0
		bool_generate_templates = 1
		my_cat_files = []
		try:
			cat_path = sys_argv[i+1]
			break
		except:
			print("Error: No path argument for template generation.")
			quit()
	if sys_argv[i].endswith(".cat"):
		bool_generate_mact = 1
		bool_generate_templates = 0
		my_cat_files.append((sys_argv[i], sys_argv[i]))
if bool_generate_templates:
	for root, dirs, files in os.walk(cat_path):
		for name in files:
			if name.endswith(".cat"):
				my_cat_files.append((root + os.sep + name, name))
if not len(my_cat_files):
	print("Error: No CAT files found.")
	quit()


# Globals for template generation
global_chelpers = []
global_thelpers = []
debug_used_generic_hashes = []

# If in generate_templates mode
# go through all CAT files, gather logic for template,
# otherwise gather logic for MACT.
for cat_path, cat_name in my_cat_files:
	# Open file
	file = open(cat_path, "rb")

	if bool_print_debug:
		print("<< {0} >>".format(cat_name))
		print("{0} -> Reading header.".format(file.tell()))

	## HEADER ##
	file_length = format_read(file, "I")
	p_data = format_read(file, "I")
	p_strings = format_read(file, "I")
	p_groups = format_read(file, "I")
	counterA = format_read(file, "I")
	counterB = format_read(file, "I")
	counterC = format_read(file, "I")
	counterD = format_read(file, "I")
	number_of_strings = format_read(file, "I")

	if bool_print_debug:
		print("{0} -> Reading variables.".format(file.tell()))

	## PARAM VARIABLE STRINGS ##
	param_variable_strings = []
	for i in range(0, number_of_strings):
		string_offset = format_read(file, "I")
		number_of_variables = format_read(file, "H")
		variable_offsets = []
		for j in range(0, number_of_variables):
			offset = format_read(file, "I")
			variable_offsets.append(offset)
		vs = ParamVariableString(
			string_offset, number_of_variables, variable_offsets)
		param_variable_strings.append(vs)

	number_of_groups = format_read(file, "I")

	## PARAM VARIABLE GROUPS ##
	param_variable_groups = []
	for i in range(0, number_of_groups):
		group_offset = format_read(file, "I")
		number_of_variables = format_read(file, "H")
		variable_offsets = []
		for j in range(0, number_of_variables):
			offset = format_read(file, "I")
			variable_offsets.append(offset)
		vg = ParamVariableGroup(group_offset, number_of_variables, variable_offsets)
		param_variable_groups.append(vg)

	if bool_print_debug:
		print("{0} -> Reading node tree.".format(file.tell()))

	def _check_hash(bytes, db):
		string = pretty_bytes(bytes)
		for hh in db:
			for h in hh.hashes:
				if string.upper() == h.upper():
					return hh.title
		return None

	def check_hash_logic(bytes):
		return _check_hash(bytes, db_hashes)

	def check_hash_generic(bytes):
		result = _check_hash(bytes, db_hashes_generic)
		if result is not None:
			if result not in debug_used_generic_hashes:
				debug_used_generic_hashes.append(result)
		return result
	
	def check_hash_title(bytes):
		return _check_hash(bytes, db_hashes_titles)

	## NODE TREE ##
	def read_cat_tree():
		offset = file.tell()
		node_type = format_read(file, "c").decode('utf-8')
		node_hash = None
		file_offset = None
		path_offset = None
		condition_offsets = []
		track_offsets = []
		children = []
		if node_type in ('b', 'l', 'n'):
			node_hash = format_read(file, "I")
			number_of_conditions = format_read(file, "B")
			for j in range(0, number_of_conditions):
				condition_offset = format_read(file, "I")
				condition_offsets.append(condition_offset)
		if node_type in ('l', 'n'):
			number_of_tracks = format_read(file, "B")
			for j in range(0, number_of_tracks):
				track_offset = format_read(file, "I")
				track_offsets.append(track_offset)
		if node_type in ('r', 'i'):
			file_offset = format_read(file, "I")
			path_offset = format_read(file, "I")
		if node_type in ('b', 'l', 'n'):
			number_of_children = format_read(file, "H")
			for j in range(0, number_of_children):
				child = read_cat_tree()
				children.append(child)
		# check for node_hash -> title replacement
		title = check_hash_title(node_hash)
		if title is not None:
			node_hash = title
		return CatNode(offset, node_type, node_hash, file_offset, path_offset, condition_offsets, track_offsets, children)

	def get_nodes(root):
		nodes = []
		nodes.append(root)
		for c in root.children:
			nodes = nodes + get_nodes(c)
		return nodes
	tree = read_cat_tree()

	if bool_print_debug:
		print("{0} -> Reading variable condition groups.".format(file.tell()))

	## VARIABLE CONDITION GROUPS ##
	variable_condition_groups = []
	for i in range(0, number_of_groups):
		offset = file.tell()
		number_of_conditions = format_read(file, "B")
		condition_offsets = []
		for j in range(0, number_of_conditions):
			condition_offset = format_read(file, "I")
			condition_offsets.append(condition_offset)
		cg = VariableConditionGroup(offset, condition_offsets)
		variable_condition_groups.append(cg)

	## DATA ##
	conditions = []
	tracks = []
	nodes = get_nodes(tree)

	# node helpers
	def noffsort(e):
		return e.offset
	chelpers = []
	thelpers = []
	vcghelpers = []
	# Function to check for repeated offsets, merge helper if offset is repeated
	def merge_helper_from_offset(node, new_offset, helper_list):
		repeated = False
		for helper in helper_list:
			if(helper.offset == new_offset):
				# Match found, append node to helper
				repeated = True
				helper.nodes.append(node)
				break
		return repeated
	# Gather condition offsets and track offsets from CAT TREE NODES
	for node in nodes:
		for offset in node.condition_offsets:
			repeated = merge_helper_from_offset(node, offset, chelpers)
			if not repeated:
				new_helper = LogicHelper([node], offset, None, None, [])
				chelpers.append(new_helper)
		for offset in node.track_offsets:
			repeated = merge_helper_from_offset(node, offset, thelpers)
			if not repeated:
				new_helper = LogicHelper([node], offset, None, None, [])
				thelpers.append(new_helper)
	# Gather condition offsets from VARIABLE CONDITION GROUPS
	for vcg in variable_condition_groups:
		for offset in vcg.condition_offsets:
			# never remove this line ever, this function is way more important than I remembered, big headaches
			repeated = merge_helper_from_offset(vcg, offset, chelpers)
			if not repeated:
				new_helper = LogicHelper([vcg], offset, None, None, [])
				chelpers.append(new_helper)
				vcghelpers.append(new_helper)
	# This spaghetti will determine condition length based on list of all nearby conditions
	# and the start of the first track
	# [0-8]COND0, [8-16]COND1, [16-32]COND2, [32-64]TRACK0
	chelpers.sort(key=noffsort)
	thelpers.sort(key=noffsort)
	if thelpers:
		pos_condition_end = thelpers[0].offset
	else:
		pos_condition_end = p_strings
	# Spaghetti
	magic_offsets = [g.condition_offsets for g in variable_condition_groups]
	magic_offsets = list(chain.from_iterable(magic_offsets))
	magic_offsets = [c.offset for c in chelpers] + \
		magic_offsets + [pos_condition_end]
	magic_offsets = list(dict.fromkeys(magic_offsets))
	magic_offsets.sort()
	# print(magic_offsets)
	# clen = [int((magic_offsets[i] - magic_offsets[i-1])/4) for i, o in enumerate(magic_offsets)][1:]

	
	# This function will run through all stored variable strings offsets and variable groups offsets
	# to try to find a match with a param offset, target_offset
	# If a match is found, it means this param's value is determined by that variable string/group
	# We'll then return the param type based on that.
	def get_type_from_references(target_offset):
		for vs in param_variable_strings:
			for offset in vs.variable_offsets:
				if target_offset == offset:
					# match
					return "string"
		for vg in param_variable_groups:
			for offset in vg.variable_offsets:
				if target_offset == offset:
					# match
					return "cg"
		return "unk"

	if bool_print_debug:
		print("{0} -> Reading condition params.".format(file.tell()))
	# condition helpers -- read params
	for i, ch in enumerate(chelpers):
		file.seek(p_data + ch.offset)
		for j in range(len(magic_offsets)):
			if ch.offset == magic_offsets[j]:
				my_length = int((magic_offsets[j+1] - magic_offsets[j]) / 4)
				for k in range(my_length):
					param_offset = file.tell() - p_data
					my_type = get_type_from_references(param_offset)
					param_value = file.read(4)
					param = Param(ch, param_offset, k, my_type, param_value)
					ch.params.append(param)
		# set condition hash to value of param[0]
		ch.hash = ch.params[0].value

	
	if bool_print_debug:
		print("{0} -> Reading track params.".format(file.tell()))
	# track helpers -- read params
	for th1 in thelpers:
		opti_offset = format_read(file, "H")
		th1.opti_offset = opti_offset
		bool_end = 0
		while not bool_end:
			param_data = format_read(file, "H")
			param_flag = get_bits(param_data, 0, 1)
			param_unk = get_bits(param_data, 1, 2)
			param_size = get_bits(param_data, 2, 3)
			param_id = get_bits(param_data, 3, 16)
			param_offset = file.tell() - p_data
			my_type = get_type_from_references(param_offset)
			if param_size:
				# 4 bytes
				param_value = file.read(4)
				param = Param(th1, param_offset, param_id, my_type, param_value)
			else:
				param_value = file.read(1)
				param = Param(th1, param_offset, param_id, "bool", param_value)
			th1.params.append(param)
			if not param_flag:
				bool_end = 1


	if bool_print_debug:
		print("{0} -> Unoptimizing tracks.".format(file.tell()))
	# unoptimize tracks
	# this code will copy all not-repeated/not-overwritten parameters
	# from the target track to the original track as dictated by opti_offset
	for th1 in thelpers:
		opti_target = 0
		if th1.opti_offset:
			opti_target = th1.offset + th1.opti_offset
		while(opti_target > 0):
			match = False
			for th2 in thelpers:
				if(opti_target == th2.offset):
					# match found
					match = True
					# ignore repeated, preserve original params
					for i, id in enumerate([p.id for p in th2.params]):
						if id not in [p.id for p in th1.params]:
							th1.params.append(th2.params[i])
					# if target has opti, continue unopti
					if th2.opti_offset:
						opti_target = th2.offset + th2.opti_offset
					else:
						opti_target = 0
			if not match:
				print("Bug: Unable to unoptimize track offset {0}.".format(p_data + th1.offset))
				break
		# resort unoptimized params
		def nidsort(e):
			return e.id
		th1.params.sort(key=nidsort)
		# set track hash to value of param[0], id=0
		for p in th1.params:
			if(p.id == 0):
				th1.hash = p.value

	if bool_print_debug:
		print("{0} -> Reading strings and reference strings.".format(file.tell()))
	## STRINGS ##
	file.seek(p_strings, 0)
	strings = []
	for i in range(0, number_of_strings):
		my_offset = file.tell() - p_strings
		string = read_string(file)
		sh = StringHelper(my_offset, string)
		strings.append(sh)
	## REFERENCE STRINGS ##
	reference_strings = []
	for node in nodes:
		offsets = []
		number_of_reference_strings = 0
		if node.type in ('r', 'i'):
			# check for repeated reference strings
			if node.file_offset not in offsets:
				offsets.append(node.file_offset)
				number_of_reference_strings += 1
			if node.path_offset not in offsets:
				offsets.append(node.path_offset)
				number_of_reference_strings += 1
		for i in range(0, number_of_reference_strings):
			my_offset = file.tell() - p_strings
			string = read_string(file)
			sh = StringHelper(my_offset, string)
			reference_strings.append(sh)

	
	# Run through all string variables to find matching offset
	# Return offset if match is found, thus this param value is a string
	def get_string_reference_from_param_offset(param):
		target_offset = param.offset
		result = None
		for vs in param_variable_strings:
			for offset in vs.variable_offsets:
				if target_offset == offset:
					# match
					result = vs.string_offset
					break
		if result is None:
			print("Warning: Unable to get string reference from {0}, param ID '{1}' value '{2}' offset '{3}'".format(pretty_bytes(param.logic_helper.hash), param.id, pretty_bytes(param.value), p_data+param.offset))
		return result
	
	
	# Run through all group variables to find matching offset
	# Return offset if match is found, thus this param value is a condition group
	def get_group_reference_from_param_offset(param):
		target_offset = param.offset
		result = None
		for vg in param_variable_groups:
			for offset in vg.variable_offsets:
				if target_offset == offset:
					# match
					result = vg.group_offset
					break
		if result is None:
			print("Warning: Unable to get group reference from {0}, param ID '{1}' value '{2}' offset '{3}'".format(pretty_bytes(param.logic_helper.hash), param.id, pretty_bytes(param.value), p_data+param.offset))
		return result
	
	def get_string_from_offset(offset):
		if offset is not None:
			for s in strings+reference_strings:
				if offset == s.offset:
					return s.string
			print("Warning: Unable to get string from offset {0}.".format(offset))
		return None

	def get_vcg_from_offset(offset):
		if offset is not None:
			for vcg in variable_condition_groups:
				if offset == vcg.offset - p_groups:
					return vcg
			print("Warning: Unable to get vcg from offset {0}.".format(offset))
		return None

	def get_db_param(db, title, id):
		for logic in db:
			if logic.title == title:
				for p in logic.params:
					if int(p.id) == int(id):
						# param match found
						return p
		return None

	def guess_param_type(param):
		# Note: Do not use get_type_from_references() here, when generating templates
		# the function will use wrong variable offsets and then return wrong results
		# If no reference and param type already is defined, don't guess
		if param.type != "unk":
			return param.type
		# Guess value based on my loose and arbitrary set of rules
		value = param.value
		if int.from_bytes(value, byteorder='little') != 0:
			param_as_int = struct.unpack("i", value)[0]
			param_as_float = struct.unpack("f", value)[0]
			if param_as_int <= 32767 and param_as_int >= -32768:
				return "int"
			elif float(param_as_float) <= 2048.0 and float(param_as_float) >= -2048.0:
				if not (float(param_as_float) <= 0.1 and float(param_as_float) >= -0.1):
					return "float"
		# Keeping return "unk" results in too many 'float' false positives
		# Keeping return "bytes" means it will only be guessed once
		return "bytes"
	
	
	def get_param_value_by_type(helper, param, type):
		value = param.value
		if type == "int":
			result = struct.unpack("i", value)[0]
		elif type == "bool":
			result = struct.unpack("B", value)[0]
			result = str(bool(result)).lower()
		elif type == "float":
			result = "{:f}".format(struct.unpack("f", value)[0])
		elif type == "string":
			# Check if param has value before checking for string references
			# (String might be hashed in this case)
			try:
				value_test = struct.unpack("i", value)[0]
			except:
				print("Error: Unable to test string value.")
				value_test = 0
			if value_test:
				# print("Info: Param ID {0} type {1} from {2} already has a value, reference check not necessary.".format(param.id, type, pretty_bytes(helper.hash)))
				result = pretty_bytes(value)
			else:
				# Param has no value therefore we'll check for string references
				result = get_string_from_offset(
					get_string_reference_from_param_offset(param))
				if result is None:
					result = '\"' + '\"'
				else:
					# append quotes to start and end
					result = '\"' + result + '\"'
		elif type == "bytes":
			string = check_hash_generic(value)
			if string is not None:
				# print("Info: Found matching string hash {0} for param value '{1}'.".format(string, pretty_bytes(value)))
				result = "h"+string
			else:
				result = pretty_bytes(value)
		elif type == "cg":
			result = pretty_bytes(0)
		else:
			result = pretty_bytes(0)
			print("Warning: Unable to handle value of param ID {0} type {1} from {2}.".format(param.id, type, pretty_bytes(helper.hash)))
		return result


	## GENERATE MACT ##
	if bool_generate_mact:
		if bool_print_debug:
			print("{0} -> Generating MACT.".format(file.tell()))
		
		mact_file_name = cat_name.rsplit(os.sep, 1)[-1].split('.')[0]+".mact"
		mact = open(mact_file_name, "w")

		def write_mact(file, root, level):
			def ntabs(level):
				return level*"\t"
			if root.hash is not None:
				if isinstance(root.hash, bytes):
					my_hash = pretty_bytes(root.hash)
				else:
					my_hash = root.hash
			else:
				my_hash = None
			if bool_write_debug:
				file.write("{0}# Pos: {1}\n".format(ntabs(level), root.offset))
			# write data based on node types
			if root.type in ('b',):
				file.write("{0}Bank {1}".format(ntabs(level), my_hash))
			elif root.type in ('l', 'n'):
				file.write("{0}Node {1}".format(ntabs(level), my_hash))
			elif root.type in ('r', 'i'):
				file.write("{0}FileReference".format(ntabs(level)))
				file.write("\n{0}{1}\n".format(ntabs(level), "{"))
				file.write("{0}fileName\t\"{1}\"\n".format(
					ntabs(level+1), get_string_from_offset(root.file_offset)))
				file.write("{0}path\t\"{1}\"\n".format(ntabs(level+1),
						get_string_from_offset(root.path_offset)))
				if(root.type in 'i'):
					file.write("{0}includeFile\ttrue".format(ntabs(level+1)))
				else:
					file.write("{0}includeFile\tfalse".format(ntabs(level+1)))
				file.write("\n{0}{1}\n".format(ntabs(level), "}"))
			# open bracket
			if root.type in ('b', 'l', 'n'):
				file.write("\n{0}{1}\n".format(ntabs(level), "{"))
				level += 1
			# condition groups and tracks
			def write_params(db, offsets, helpers, level):
				for offset in offsets:
					match = False
					for helper in helpers:
						if offset == helper.offset:
							match = True
							# match found
							my_hash = check_hash_logic(helper.hash)
							if my_hash is None:
								print(helper)
								my_hash = pretty_bytes(helper.hash)
								# jank
								if helper.hash and my_hash == "NULL":
									my_hash = hash_title(helper.hash)
									my_hash = pretty_bytes(helper.hash)
							if bool_write_debug:
								file.write("\n{0}# Pos: {1}; Offset: {2}".format(
									ntabs(level), p_data+offset, offset))
							file.write("\n{0}{1}".format(ntabs(level), my_hash))
							file.write("\n{0}{1}\n".format(ntabs(level), "{"))
							level += 1
							for p in helper.params:
								# skip pid 0 like original files
								if bool_skip_id_zero and p.id == 0:
									continue
								# Attempt to match param with database
								param_match = get_db_param(db, my_hash, p.id)
								if param_match is None:
									if bool_has_db_tracks or bool_has_db_conditions:
										print("Warning: Unable to match param ID {0} from {1} with database.".format(p.id, my_hash))
									param_name = "[{value:0{digits}}]".format(
										value=int(p.id), digits=number_of_param_digits)
									param_type = get_type_from_references(p.offset)
									if param_type == "unk":
										param_type = "bytes"
									param_value = get_param_value_by_type(helper, 
										p, param_type)
								else:
									param_name = param_match.title
									# check for references, override
									param_type = get_type_from_references(p.offset)
									if param_type == "unk":
										param_type = param_match.type
									param_value = get_param_value_by_type(helper, 
										p, param_type)
								# If p.type is CG, treat as CG
								# param_type is irrelevant in this case
								if p.type in ('cg'):
									if param_type not in ('cg') and (bool_has_db_tracks or bool_has_db_conditions):
										print("Warning: Param ID {0} from {1} is treated as condition group but it's template disagrees.".format(p.id, my_hash))
									vcg = get_vcg_from_offset(get_group_reference_from_param_offset(p))
									if vcg is not None and vcg != "NULL":
										if bool_write_debug:
											file.write("{0}# Pos: {1}; Children: {2}\n".format(
												ntabs(level), vcg.offset, len(vcg.condition_offsets)))
									file.write("{0}{1}".format(ntabs(level), param_name))
									file.write("\n{0}{1}".format(ntabs(level), "{"))
									if vcg is not None and vcg != "NULL":
										write_params(db_conditions, vcg.condition_offsets,
													chelpers, level+1)
									file.write("\n{0}{1}\n".format(ntabs(level), "}"))
								else:
									# Otherwise, regular write param value
									file.write("{0}{1}\t{2}\n".format(
										ntabs(level), param_name, param_value))
							level -= 1
							file.write("{0}{1}".format(ntabs(level), "}"))
					if not match:
						print("Error: Unable to match param offset {0}.".format(offset))
			# condition group
			if root.type in ('b', 'l', 'n'):
				file.write("{0}ConditionGroup".format(ntabs(level)))
				file.write("\n{0}{1}".format(ntabs(level), "{"))
				write_params(db_conditions, root.condition_offsets,
							chelpers, level+1)
				file.write("\n{0}{1}\n".format(ntabs(level), "}"))
			# tracks
			if root.type in ('l', 'n'):
				file.write("{0}Tracks".format(ntabs(level)))
				file.write("\n{0}{1}".format(ntabs(level), "{"))
				write_params(db_tracks, root.track_offsets, thelpers, level+1)
				file.write("\n{0}{1}\n".format(ntabs(level), "}"))
			# children
			for c in root.children:
				write_mact(file, c, level)
			if root.type in ('b', 'l', 'n'):
				level -= 1
				file.write("{0}{1}\n".format(ntabs(level), "}"))
		write_mact(mact, tree, 0)	
		# Close file
		file.close()
	# Each file will add to global helpers for template generation
	global_chelpers += chelpers
	global_thelpers += thelpers


## GENERATE HELPERS (UNUSED) ##
def write_helpers(file, helpers):
	for h in helpers:
		my_offset = h.offset
		my_hash = check_hash_logic(h.hash)
		if my_hash is None:
			my_hash = pretty_bytes(h.hash)
		if bool_write_debug:
			file.write("# Pos: {0}\n".format(p_data+my_offset))
		file.write(my_hash+"\n")
		for i, p in enumerate(h.params):
			if bool_skip_id_zero and p.id == 0:
				continue
			my_id = str(p.id)
			my_name = "param" + \
				"{value:0{digits}}".format(
					value=int(my_id), digits=number_of_param_digits)
			my_type = p.type
			if bool_guess_param_types:
				my_type = guess_param_type(p)
			my_value = get_param_value_by_type(h, p, my_type)
			file.write("\t{0}\t{1}\t{2}\t{3}\n".format(
				my_id, my_name, my_value, my_type))


## GENERATE TEMPLATES ##
def write_template(file, helpers):
	def hashsort(e):
		title = check_hash_logic(e.hash)
		if title is None:
			return pretty_bytes(e.hash)
		else:
			return title

	def idsort(e):
		return e.id
	# guess all params early before merging for higher chances
	# of finding good value for guessing
	for h in helpers:
		for p in h.params:
			if bool_guess_param_types:
				p.type = guess_param_type(p)
	# sort
	helpers.sort(key=hashsort)
	# spaghetti merge
	number_of_helpers = len(helpers)
	if number_of_helpers:
		item = helpers[0]
	i = 0
	new_helpers = []
	while i < (number_of_helpers - 1):
		my_title = check_hash_logic(item.hash)
		next_item = helpers[i+1]
		if item.hash == next_item.hash:
			# match found
			# merge identified params
			for p1 in item.params:
				for p2 in next_item.params:
					if p1.id == p2.id:
						if p1.type == "unk" and p2.type != "unk":
							p1.type = p2.type
			# merge missing params
			param_ids = [p.id for p in item.params]
			for p in next_item.params:
				if p.id not in param_ids:
					item.params.append(p)
			# sort params
			item.params.sort(key=idsort)
			i = i + 1
		else:
			new_helpers.append(item)
			item = next_item
	# only set all remaining unk types to bytes after merging
	# this lazy fix should prevent conditionGroups being set to type bytes
	for h in helpers:
		for p in h.params:
			if p.type == "unk":
				p.type = "bytes"
	# write
	for h in new_helpers:
		my_name = check_hash_logic(h.hash)
		my_hash = pretty_bytes(h.hash)
		if my_name is None:
			file.write("{0}\n".format(my_hash))
		else:
			file.write("{0}\t{1}\n".format(my_name, my_hash))
		for i, p in enumerate(h.params):
			if bool_skip_id_zero and p.id == 0:
				continue
			my_id = str(p.id)
			my_name = "param" + \
				"{value:0{digits}}".format(
					value=int(my_id), digits=number_of_param_digits)
			my_type = p.type
			my_value = get_param_value_by_type(h, p, my_type)
			file.write("\t{0}\t{1}\t{2}\n".format(my_id, my_name, my_type))


if bool_generate_templates:
	if not os.path.exists("TEMPLATES"):
		os.mkdir("TEMPLATES")
	tout = open(fn_dbt, "w")
	write_template(tout, global_thelpers)
	# write_helpers(tout, global_thelpers)
	tout.close()
	cout = open(fn_dbc, "w")
	write_template(cout, global_chelpers)
	# write_helpers(cout, global_chelpers)
	cout.close()
	# debug write used generic hashes
	'''
	debug_used_generic_hashes.sort()
	fn_out_generic_hashes = open("generic_hashes.txt", "w")
	for string in debug_used_generic_hashes:
		fn_out_generic_hashes.write(string+"\n")
	'''

# End #
print("-> Done.")
quit()
