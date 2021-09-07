#!/usr/bin/python3
# -*- coding: UTF-8 -*-

import sys
import logging
import re
import glob
import json
import unittest
import argparse
import os
import traceback
import subprocess
import tempfile
from contextlib import contextmanager
import io
import inspect
import copy

#
SYNTAX_ERROR_FEEDBACK_MSG = 'בקוד יש שגיאת/ות נוראיות, האם אתה יודע בכלל פייתון?!. דבגו את הקוד והגישו שוב.'
SYNTAX_ERROR_FEEDBACK_MSG_ORIGIN = 'בקוד יש שגיאת/ות תחביר. דבגו את הקוד והגישו שוב.'

#SYNTAX_ERROR_FEEDBACK_MSG = 'בקוד יש שגיאת/ות תחביר. פרטי השגיאה הראשונה שזוהתה מופיעים במסגרת שלפניכם (מספר השורה, סוג השגיאה).- מיקום שגיאת syntax מסומן ב-^- indentation error (שגיאת הזחה): לרוב בגלל tab/רווח חסר או מיותר. במקרה של שגיאת הזחה, שימו לב שלעתים השגיאה מדווחת על השורה שלאחר ההזחה השגויה.'

#
SIGNATURE_FEEDBACK_MSG = ('חתימת הפונקציה בכלל לא בכיוון, שווה לשקול לשנות מקצוע ולוותר על החלום.\n' +
                          'חתימת הפונקציה המצופה:\n' +
                          '{}\n')
SIGNATURE_FEEDBACK_MSG_ORIGIN = ('חתימת הפונקציה בקוד אינה תואמת לנדרש במטלה.\n' +
                          'חתימת הפונקציה המצופה:\n' +
                          '{}\n')
#
FUNC_NAME_FEEDBACK_MSG = (' ושם הפונקציה לא בכיווןן דני רובין ' +
                          '{}\n')
FUNC_NAME_FEEDBACK_MSG_ORIGIN = ('שם הפונקציה אינו תואם לנדרש במטלה.' +
                          'שם הפונקציה המצופה:\n' +
                          '{}\n')
#

CODE_ERROR_FEEDBACK_MSG = 'בקוד יש שגיאת/ות וריצתו לא הושלמה. דבגו את הקוד והגישו שוב.'
FUNC_ERROR_FEEDBACK_MSG = 'בהרצת הפונקציה התרחשה שגיאה. דבגו את הקוד והגישו שוב.'

INPUT_COMMAND_ERROR_FEEDBACK_MSG = 'אין צורך לעשות שימוש בפקודה לקליטת קלט מהמשתמש, הסירו את הפקודה מהקוד והגישו שוב - input'


DIRECTORY_PATH = os.path.dirname(os.path.realpath(__file__))

test_case = unittest.TestCase()

JSON_PATH = 'student/json'
CODE_PROBLEM_ID = 'program'
TEST_TYPES = {
    'equal': {'method_name': 'assertEqual'},
    'not_equal': {'method_name': 'assertNotEqual'},
    'count_equal': {'method_name': 'assertCountEqual'}
}

INGINIOUS_MODE = 'inginious'
STAND_ALONE_MODE = 'stand_alone'

RST_MSGBLOCK_MSG_LIMIT = 20000


class PrintOutException(Exception):
    pass  # Custom exception


@contextmanager
def stdout_redirector(stream):
    old_stdout = sys.stdout
    sys.stdout = stream
    try:
        yield
    finally:
        sys.stdout = old_stdout


def indent(text, amount, ch=' '):
    padding = amount * ch
    return ''.join(padding + line for line in text.splitlines(True))


logging.basicConfig(format='%(levelname)s :: %(message)s', level=logging.DEBUG,
                    handlers=[logging.StreamHandler(sys.stdout)])


def is_input_in_code(code):
    return re.search(r'input\(.*\)', code) is not None


def is_include_in_code(code, lib):
    return re.match('#include[<"]{}.h[>"]'.format(lib), code) is not None


def is_as_student_string(code):
    return code.startswith('#asstudent')


def extract_params(sig):
    left_boundry = sig.find('(') + 1
    right_boundry = sig.find(')')
    args_str = sig[left_boundry:right_boundry]
    args_str = args_str.replace(' ', '')
    return args_str.split(',')


def extract_signature(user_input):
    left_boundry = user_input.find(' ') + 1
    right_boundry = user_input.find(')') + 1
    signature_str = user_input[left_boundry:right_boundry]
    return signature_str


def check_args(method_signature, user_input, method_name):
    expected_args = extract_params(method_signature)
    user_input_signature = extract_signature(user_input)
    inspected_func = inspect.getfullargspec(globals()[method_name])
    inspected_args = inspected_func.args
    if(inspected_args != expected_args):
        '''
        text = 'הארגומנטים שהתקבלו אינם תואמים את הציפיות. \n '
        text += 'ארגומנטים צפויים: '
        #text += '(' + ','.join(expected_args) + ')'
        text += method_signature
        text += 'ארגומנטים שהתקבלו: '
        #text += '(' + ','.join(inspected_args) + ')'
        text += user_input_signature
        '''
        text = SIGNATURE_FEEDBACK_MSG.format(method_signature)
        if MODE != STAND_ALONE_MODE:
            subprocess.run(['feedback-result', 'failed'], check=True)
            subprocess.run(['feedback-msg', '-a', '-m', text], check=True)
        else:
            logging.error('feedback-result, failed')
            logging.error('feedback-msg, ' + text)

        sys.exit(-1)


def run_single_test(snr_path, json_output, external_index, user_input):
    external_index_string = str(external_index)
    json_data = json.load(open(snr_path, 'r'))
    method_name = json_data.get('method_name', 'solution')

    # if the signature is not exists this will fall because the key is not exist
    try:
        globals()[method_name]
    except Exception as e:
        text = FUNC_NAME_FEEDBACK_MSG.format(method_name)

        if MODE != STAND_ALONE_MODE:
            subprocess.run(['feedback-result', 'failed'], check=True)
            subprocess.run(['feedback-msg', '-a', '-m', text], check=True)
        else:
            logging.error('feedback-result, failed')
            logging.error('feedback-msg, ' + text)

        sys.exit(-1)

    student_method_sent = globals()[method_name]
    test_data = json_data['test']
    logging.debug('Iterating over ' + repr(snr_path))
    # supporting multi tests in one json files. currently not used
    test = test_data[0]

    # ugly hack to support tuple testing
    if method_name == 'sort_prices':
        test['expected'] = [tuple(item) for item in test['expected']]
        test['args'] = [[tuple(item) for item in test['args'][0]]]

    # 08-01-04
    elif method_name == 'mult_tuple':
        test['expected'] = tuple([tuple(item) for item in test['expected']])
        test['args'] = [tuple(item) for item in test['args']]

    # 09-02-01
    elif method_name == 'my_mp3_playlist':
        test['expected'] = tuple(test['expected'])

    # 09-05-01
    elif method_name == 'choose_word':
        test['expected'] = tuple(test['expected'])

    json_output, success = test_the_method(
        json_data, test, student_method_sent, snr_path, external_index_string, json_output, method_name)

    return json_output, success


def test_the_method(json_data, test, student_method_sent, snr_path, external_index_string, json_output, method_name):
    success = False
    returned_value = None
    captured_output = None
    if TEST_TYPES.get(test['type']):
        test_method_name = TEST_TYPES[test['type']]['method_name']
        test_method = getattr(test_case, test_method_name)
        expected_value = test['expected']
        error_message = test['error']
        expected_printouts = test.get('expected_stdout', [])
        error_message_printouts = test.get('error_message_in_case_of_print_outs', '')
        args = copy.deepcopy(test['args'])

        try:

            # in order capture the stout  -> https://eli.thegreenplace.net/2015/redirecting-all-kinds-of-stdout-in-python/
            # in some case we want to test it
            f = io.StringIO()

            with stdout_redirector(f):
                try:
                    returned_value = student_method_sent(*args)
                except Exception as e:
                    result = create_result(json_data, False, 'אי הצלחה')
                    result['feedback'] = {'text': FUNC_ERROR_FEEDBACK_MSG,
                                          'type': 'Exception',
                                          'technical_error': repr(e)}
                    returned_value = 'התרחשה שגיאה'
                    result['actual_stdout'] = captured_output
                    result['expected'] = test['expected']
                    result['method_name'] = method_name
                    result['returned_value'] = returned_value
                    result['arguments_sent'] = test['args']
                    json_output[external_index_string] = result
                    success = False
                    return json_output, success

            if expected_printouts:

                captured_output = f.getvalue()
                # flow: false
                # strictness: ~true (just removing spaces at the beginning and end)
                captured_output_lines = captured_output.strip().splitlines()

                if expected_printouts != [line.strip() for line in captured_output_lines]:
                    raise PrintOutException

            try:
                test_method(returned_value, expected_value)
                result = create_result(json_data, True, 'הצלחה')
                success = True
            except AssertionError as e:
                result = create_result(json_data, False, 'אי הצלחה')
                success = False
                raise

        except PrintOutException as e:
            file_name = snr_path.split('/')[-1]
            logging.error(file_name + ' print out failed!!! error message is ' + repr(e))
            result = create_result(json_data, False, 'אי הצלחה')
            result['feedback'] = {'text': 'PrintOutException',
                                  'type': 'ERR',
                                  'technical_error': repr(e)}
        except Exception as e:
            file_name = snr_path.split('/')[-1]
            logging.error(file_name + ' failed!!! error message is ' + repr(e))
            result = create_result(json_data, False, 'אי הצלחה')
            result['feedback'] = {'text': error_message,
                                  'type': 'ERR',
                                  'technical_error': repr(e)}

        result['actual_stdout'] = captured_output
        result['expected'] = test['expected']
        result['method_name'] = method_name
        result['returned_value'] = returned_value
        result['arguments_sent'] = test['args']
        json_output[external_index_string] = result
    else:
        logging.debug(str(test['type']) + ' NOT found ' + repr(TEST_TYPES))

    return json_output, success


def handle_tests(user_input, is_staff):
    json_output = {}
    n_snr = 0
    n_success = 0
    logging.debug('Iterating over JSON files')
    path_to_explore = JSON_PATH
    if MODE == STAND_ALONE_MODE:
        path_to_explore = DIRECTORY_PATH + '/tasks/' + TASK_NAME + '/' + path_to_explore

    ### Compilation Syntax Check ###

    # validate_no_input(user_input)
    validate_compilation(user_input, is_staff)

    ### End Of Compilation Syntax Check ###

    try:
        exec(user_input, globals())
    except Exception as e:
        if MODE != STAND_ALONE_MODE:
            subprocess.run(['feedback-result', 'failed'], check=True)
            subprocess.run(['feedback-msg', '-a', '-m',
                            CODE_ERROR_FEEDBACK_MSG], check=True)
        else:
            logging.error('feedback-result, failed')
            logging.error(CODE_ERROR_FEEDBACK_MSG)

        sys.exit(-1)

    relevant_test_json_files = sorted(glob.glob(path_to_explore + '/*.json'))
    if len(relevant_test_json_files) > 0:
        test_student_method_sent_signature(path_to_explore, user_input)

        # run the test
        for i, snr_path in enumerate(sorted(glob.glob(path_to_explore + '/*.json'))):
            n_snr += 1
            json_output, success = run_single_test(snr_path, json_output, i, user_input)
            if success:
                n_success += 1

    results = {'n_snr': n_snr, 'n_success': n_success}

    logging.debug(json_output)
    logging.debug(results)
    return json_output, results


def test_student_method_sent_signature(path_to_explore, user_input):

    first_file = os.listdir(path_to_explore)[0]

    json_data = json.load(open(path_to_explore + '/' + first_file))
    method_name = json_data.get('method_name', 'solution')
    method_signature = json_data.get('method_signature', 'solution')

    # if the signature is not exists this will fall because the key is not exist
    try:
        globals()[method_name]
    except Exception as e:
        text = FUNC_NAME_FEEDBACK_MSG.format(method_name)

        if MODE != STAND_ALONE_MODE:
            subprocess.run(['feedback-result', 'failed'], check=True)
            subprocess.run(['feedback-msg', '-a', '-m', text], check=True)
        else:
            logging.error('feedback-result, failed')
            logging.error('feedback-msg, ' + text)

        sys.exit(-1)

    # check full signature include arguments
    if(method_signature != 'solution'):
        check_args(method_signature, user_input, method_name)


def validate_no_input(user_input):
    if is_input_in_code(user_input):
        logging.error('There is an input command in code!')

        if MODE == STAND_ALONE_MODE:
            logging.error('feedback-result, failed')
            logging.error(SYNTAX_ERROR_FEEDBACK_MSG)
        else:
            subprocess.run(['feedback-result', 'failed'], check=True)
            subprocess.run(['feedback-msg', '-a', '-m',
                            INPUT_COMMAND_ERROR_FEEDBACK_MSG], check=True)

        sys.exit(-1)

    logging.info('No input command in code!')


def validate_compilation(user_input, is_staff):

    CODE_PATH = os.path.dirname(os.path.abspath(__file__))

    f = tempfile.NamedTemporaryFile(dir=CODE_PATH, suffix='.py')

    with open(f.name, 'w') as code_file:
        code_file.write(user_input)

    logging.debug('Code saved to ' + CODE_PATH)

    if MODE == INGINIOUS_MODE:
        compiler_args = ['python3.5', '-m', 'py_compile', code_file.name]
    if MODE == STAND_ALONE_MODE:
        compiler_args = ['python3', '-m', 'py_compile', code_file.name]
    logging.info(' '.join(compiler_args))
    compiler_result = subprocess.run(
        compiler_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    logging.debug('py_compile return code <{}>'.format(compiler_result.returncode))

    f.close()
    code_file.close()
    if compiler_result.returncode != 0:
        logging.error('Compilation failed!')
        logging.error(compiler_result.stdout)

        if MODE == STAND_ALONE_MODE:
            logging.error('feedback-result, failed')
            logging.error(SYNTAX_ERROR_FEEDBACK_MSG)
        else:
            subprocess.run(['feedback-result', 'failed'], check=True)
            subprocess.run(['feedback-msg', '-a', '-m',
                            SYNTAX_ERROR_FEEDBACK_MSG], check=True)

        add_additional_staff_data_if_error(is_staff, compiler_result)
        sys.exit(-1)

    logging.info('Compilation succeeded!')


def add_additional_staff_data_if_error(is_staff, compiler_result):
    if is_staff:
        if MODE != STAND_ALONE_MODE:
            compiler_msg = subprocess.run(['rst-code', '-c', compiler_result.stdout],
                                          stdout=subprocess.PIPE, check=True).stdout
            compiler_msg = subprocess.run(['rst-msgblock', '-c', 'danger', '-t', 'Compiler Output', '-m', compiler_msg],
                                          check=True, stdout=subprocess.PIPE).stdout
            subprocess.run(['feedback-msg', '-a', '-m', compiler_msg], check=True)

        else:
            logging.error('compilation failed')


def create_result(json_data, result_bool, result_text):
    result = {}
    result['bool'] = result_bool
    result['text'] = result_text
    json_data['result'] = result
    return json_data


def collect_input():
    logging.debug('Checking is staff')

    username = subprocess.run(['getinput', 'username'], stdout=subprocess.PIPE, check=True).stdout
    username = str(username, encoding='utf8')

    OUTPUT_HTML_PAGE = subprocess.run(
        ['getinput', 'html_template'], stdout=subprocess.PIPE, check=True).stdout
    OUTPUT_HTML_PAGE = str(OUTPUT_HTML_PAGE, encoding='utf8')

    logging.debug('Username <{}>' .format(username))
    is_staff = (re.match('^s[0-9]+$', username) is None)
    logging.info('is_staff=' + str(is_staff))

    logging.debug('Getting code of problem id <{}>'.format(CODE_PROBLEM_ID))
    code = subprocess.run(['getinput', CODE_PROBLEM_ID], stdout=subprocess.PIPE, check=True).stdout
    code = str(code, encoding='utf8')

    return OUTPUT_HTML_PAGE, code, is_staff


def collect_stubbed_input():
    OUTPUT_HTML_PAGE = '{feedback_json}'
    school_solution_path = DIRECTORY_PATH + '/PTBS/' + TASK_NAME + '.py'
    with open(school_solution_path, 'r') as f:
        code = f.read()
    is_staff = 'dont care'

    return OUTPUT_HTML_PAGE, code, is_staff


def deliver_results(OUTPUT_HTML_PAGE, output_json={}, results={}):
    username = subprocess.run(['getinput', 'username'], stdout=subprocess.PIPE, check=True).stdout
    username = str(username, encoding='utf8')

    
    total_scenario_feedback = output_json
    for item, i in enumerate(total_scenario_feedback):
        if(total_scenario_feedback[str(item)]['returned_value'] != 'התרחשה שגיאה'):
            total_scenario_feedback[str(item)]['returned_value'] = repr(
                total_scenario_feedback[str(item)]['returned_value'])
        total_scenario_feedback[str(item)]['expected'] = repr(
            total_scenario_feedback[str(item)]['expected'])
        if(type(total_scenario_feedback[str(item)]['arguments_sent']) == list):
            for arg, j in enumerate(total_scenario_feedback[str(item)]['arguments_sent']):
                total_scenario_feedback[str(item)]['arguments_sent'][arg] = repr(
                    total_scenario_feedback[str(item)]['arguments_sent'][arg])


    scenario_feedback = u'eval(' + json.dumps(total_scenario_feedback) + u')'
    scenario_feedback = u'eval(' + json.dumps(total_scenario_feedback) + u')'

    scenario_output_html = OUTPUT_HTML_PAGE.format(
        feedback_json=scenario_feedback)
    feedback_output_html = '.. raw:: html' + '\n' + indent(scenario_output_html, 4)


    logging.debug('scenario_feedback Updating')
    all_student_tasks = list(sorted(glob.glob(JSON_PATH + '/*.json')))
    logging.debug(all_student_tasks)
    two_parts = feedback_output_html.split('</table>')
    new_section_start = '''</table>
            <div class="feedback_box" id="code_feedback"> '''
    new_section_end = '</div>'

    all_clues = ''
    big_clue_data = ''
    # hagit: initiate 2 counters and sum all values of "None" or "התרחשה שגיאה"
    count_None = 0
    count_error_occure = 0
    for item, i in enumerate(total_scenario_feedback):
        if(total_scenario_feedback[str(item)]['returned_value'] == 'התרחשה שגיאה'):  
            count_error_occure += 1
        if(total_scenario_feedback[str(item)]['returned_value'] == 'None'):
            count_None += 1
    ####
    
    for index, key in enumerate(list(sorted(total_scenario_feedback.keys()))):
        current_student_file_path = all_student_tasks[index]
        logging.debug('Running over scenerio number - ' + str(key))
        logging.debug('And  scenerio file - ' + current_student_file_path)
        
        with open(current_student_file_path) as f:
            file_content = json.load(f)
        if("feedback" in total_scenario_feedback[key]):
            logging.debug("There is an error at - " + key + " so appending clue!")
            if('CLUE' in list(file_content.keys())):
                logging.debug("Found better response. Updating clue to - " + file_content['CLUE'])
                all_clues += file_content['CLUE'] + " <br/> "
            else :
                logging.debug("No CLUE for this!")

        if('MAIN_CLUE' in list(file_content.keys())):
            big_clue_data += file_content['MAIN_CLUE']
            
    # hagit: check if all returen values are "None" or "התרחשה שגיאה"
    # if so, enter the appropriate text   
    if (count_None == item + 1):
        all_clues = "הרצת הפונקציה מסתיימת מבלי שמוחזרת תוצאה. אולי אין קריאה ל-return, או שהקריאה ל-return היא ללא ערך מוחזר? אולי ההרצה לא מגיעה לקריאה ל-return בשל תנאי שאינו מתקיים?"
    if (count_error_occure == item + 1):
        all_clues = "בקוד ישנה שגיאה שאינה שגיאת תחביר, כמו למשל שימוש במשתנה או בפונקציה שאינם מוגדרים. <br/>שימו לב: איות לא נכון של הערכים הבוליאנים False, True גם הוא למעשה שימוש במשתנה לא מוגדר"
    ###
    
    if(all_clues == ''):
        specific_clue_section = '</table>'
    else:
        if (count_None < item + 1 and count_error_occure < item + 1): 
        # hagit: add this header to the msg, but only if not all "None" or "התרחשה שגיאה"
            all_clues = " כל תרחיש בודק קלט עם מאפיין מסוים.<br/>" + all_clues
       ###
        specific_clue_section = new_section_start + all_clues + new_section_end






    ## ADD NEW EXAMPLE BY EXTERNAL HTML ##
    taskid = '0.0.0'
    with open('task.yaml', "r", encoding='utf-8') as f:
        file_content_lines = f.readlines()
        for line in file_content_lines:
            if line[0:4] == 'name' :
                taskid = line.split()[1]

    toggle_sector = '''<script>
    var USERNAME = "'''+username+'''"
    var TASK_ID = "'''+taskid+'''"
    
    function fetch_server_data(id) {
        const query_body = {
            'username':USERNAME,
            'time': new Date().toISOString(),
            'taskid': TASK_ID,
            'section_click': id
        }
        var settings = {
            "url": "http://35.85.48.63:7500/save_data",
            "method": "POST",
            "timeout": 0,
            "headers": {
                "Content-Type": "application/json"
            },
            "data": JSON.stringify(query_body),
        };
        $.ajax(settings).done(function (response) {
            console.log(response);
        });
        console.log(query_body)
    }

    function toggle_sector(id){
        if(document.getElementById(id).style.display == 'block') document.getElementById(id).style.display = 'none';
        else {
            document.getElementById(id).style.display = 'block';
            // Fetch server (?)
            fetch_server_data(id);
        } 
    }
    </script>
    '''
    style_section = '''<style>
        .clue_section {
            margin: 15px -15px -10px 0px; padding:5px 20px; font-family:sans-serif ;color:#00729A; cursor:pointer; font-size:20px; text-align:right; 
        }
        .solution_section_link:hover ,
        .clue_section:hover {
            margin-left:15px; border: 1px solid black; padding:4px 19px;
        }
        .solution_section_link {
            padding:5px 20px;font-family:sans-serif ;color:#00729A !important; cursor:pointer; font-size:20px; text-align:right;  margin-right:-15px; display:block;text-decoration:none !important;
        }
        .feedback_box {
           margin-right:-15px;margin-left:15px; font-size:16px; text-align:right; direction:rtl; padding:15px; background-color: #e7e7e7; border:1px solid #bbb;
        }
        #code_clue {
            display:none;
        }
        #close_clue {
            color: #00729A; cursor: pointer;
        }
    </style>
    '''

    def create_solution():
        def map_taskid_to_solution(taskid):
            split_task = taskid.split('.')
            split_task = list(map(lambda x: "0"+str(x), split_task))
            split_task = '-'.join(split_task)
            return split_task

        logging.debug('Task ID is - ' + taskid)
        return  '''
        <a onclick="fetch_server_data('code_solution')" class="solution_section_link" target="_blank" href="https://s3.eu-west-1.amazonaws.com/data.cyber.org.il/virtual_courses/python/autofeedback/solutions/''' + map_taskid_to_solution(taskid) + '''.py">
            פתרון לדוגמה <span style="font-size:14px">(חשוב לזכור שלרוב יש יותר מאפשרות אחת לקוד נכון!)</span>
        </a><br/>
        '''
        
    def create_clue():
        clue_section = ''
        logging.debug('user name is - ' + username)
        if(not all_clues == ''):
            if(not big_clue_data == '') :
                clue_section = '''<div class="clue_section"
                    onclick="toggle_sector('code_clue')">
                    רמז לפתרון 
                </div><br/><div class="feedback_box" id='code_clue'>''' + big_clue_data + '''<div 
                onclick="toggle_sector('code_clue')" id="close_clue">
                הסתר את הרמז</div></div>'''
        return clue_section

    casing_section = style_section + toggle_sector 
    main_clue_and_solution_section = casing_section + create_clue() + create_solution() 

    # Inserting new content to HTML
    feedback_output_html = two_parts[0] + specific_clue_section + main_clue_and_solution_section + two_parts[1]



    # calculate grade
    n_snr = results.get('n_snr', 0)
    n_success = results.get('n_success', 0)
    if n_snr == n_success:
        result = 'success'
        grade = '100'

    else:
        result = 'failed'
        grade = str(int(100 * n_success / n_snr))

    logging.info('++++++++++++++++++++++++++++++')
    logging.info('Result: ' + result)
    logging.info('Grade: ' + grade)
    logging.info('++++++++++++++++++++++++++++++')

    if MODE == STAND_ALONE_MODE:
        a = 1
        # print the results and who failed

    else:
        subprocess.run(['feedback-msg', '-a'], stdout=subprocess.PIPE,
                       input=feedback_output_html.encode('utf8'), check=True)
        subprocess.run(['feedback-result', result], check=True)
        subprocess.run(['feedback-grade', grade], check=True)
        subprocess.run(['definetest', 'grade', grade], check=True)

    logging.debug('Done All!')


def main():

    # input
    # is_staff in not used currently
    if MODE == STAND_ALONE_MODE:
        OUTPUT_HTML_PAGE, code, is_staff = collect_stubbed_input()
    else:
        OUTPUT_HTML_PAGE, code, is_staff = collect_input()
    # tests
    output_json, results = handle_tests(code, is_staff)

    # deliver results
    deliver_results(OUTPUT_HTML_PAGE, output_json=output_json, results=results)


if __name__ == '__main__':
    try:
        # exmple running this file as stand alone
        # python3 run.python.unittest.py -T Example-Unittest
        global MODE
        global TASK_NAME
        parser = argparse.ArgumentParser(description='Run for python unit tests.')
        parser.add_argument('--task-name', '-T',
                            help='in stand alone mode, '
                                 'the script will load the PTBS solution from the '
                                 'relevant directory by the <directory_name>.py convention')
        args = parser.parse_args()

        TASK_NAME = args.task_name
        if TASK_NAME is not None:
            MODE = STAND_ALONE_MODE
        else:
            MODE = INGINIOUS_MODE

        main()
        sys.exit(0)

    except Exception as err:

        logging.exception('Exception in main! ' + repr(err))

        text = 'התרחשה תקלה במערכת. נסו להגיש שוב. אם התקלה חוזרת, אנא פנו למדריך. '
        text += repr(err)
        text += traceback.format_exc()

        subprocess.run(['feedback-result', 'crash'], check=True)
        subprocess.run(['feedback-msg', '-a', '-m', text], check=True)

        sys.exit(-1)























































