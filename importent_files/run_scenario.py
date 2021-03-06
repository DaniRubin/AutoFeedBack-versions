#!/usr/bin/python3
# -*- coding: UTF-8 -*-

'''
TODO
====
2. Refactor flow of handeling Scenario output
'''

RESOURCES_HTML_URL = 'https://cdn.rawgit.com/shlomihod/scenario/v2.1.0/scenario/formats/html/'

import sys
import subprocess
import logging
import re
import glob
import traceback
import json


def indent(text, amount, ch=' '):
    padding = amount * ch
    return ''.join(padding + line for line in text.splitlines(True))


class EmptyScenarioOutputError(Exception):
    pass


class InvalidScenarioFeedbackJSONError(Exception):
    pass


class SNRFileError(Exception):
    pass


class ScenarioProgramError(Exception):
    pass


class INGIniousIORedirectError(Exception):
    pass


class RunScenarioError(Exception):
    pass


RUN_SCENARIO_SH = {'path': 'student/run_scenario.sh',
                   'content':
                   '''
                        #!/usr/bin/bash
                        export TERM=xterm
                        mkdir temp
                        
                        cp student/program.py temp/program.py

                        if [ -d "student/files" ]; then
                            cp -r student/files/* temp/
                        fi

                        cd temp

                        scenario "python3.5 ./program.py" ../$1 $3 -f json -i $2
                        ret=$?
                        cd ..
                        exit $ret
                        '''
                   }

JSON_PATH = 'student/json'
HTML_PATH = 'student/html'
CODE_PROBLEM_ID = 'program'
CODE_PATH = 'student/program.py'
# EXCECUTABLE_PATH = 'student/program.o'

# ADDRESS_EXCECUTABLE_PATH = 'student/address.o'
# MEMORY_EXCECUTABLE_PATH = 'student/memory.o'

SCENARIO_PROMPT = r'C:\Selfpy> python program.py'

MAX_FEEDBACK_MSG_SIZE = 1000**2  # 1 MB

logging.basicConfig(format='%(levelname)s :: %(message)s', level=logging.DEBUG,
                    handlers=[logging.StreamHandler(sys.stdout)])


def is_include_in_code(code, lib):
    return re.search('#include\s*[<"]{}.h[>"]'.format(lib), code) is not None


def is_as_student_string(code):
    return code.startswith('#asstudent')


def checking_is_staff():
    logging.debug('Checking is staff')

    username = subprocess.run(['getinput', 'username'],
                              stdout=subprocess.PIPE, check=True).stdout
    username = str(username, encoding='utf8')

    logging.debug('Username <{}>' .format(username))
    is_staff = (re.match('^s[0-9]+$', username) is None)
    logging.info('is_staff=' + str(is_staff))

    return is_staff


def main(is_staff):

    logging.debug('Create run_scenario.sh')
    with open(RUN_SCENARIO_SH['path'], 'w') as f:
        f.write(RUN_SCENARIO_SH['content'])

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

    with open(CODE_PATH, 'w') as code_file:
        code_file.write(code)

    logging.debug('Code saved to ' + CODE_PATH)

    if is_staff and is_as_student_string(code):
        is_staff = False
        logging.info('Run as student, i.e. is_staff=' + str(is_staff))
    '''
    ### Code Pre-Compilation Checks ###

    logging.debug('Checking if there is system("pause") in code')

    if re.search(r'system\("pause"\)', code, re.IGNORECASE) is not None:
        logging.info('system("pause") in code')

        subprocess.run(['feedback-result', 'failed'], check=True)
        subprocess.run(['feedback-msg', '-a', '-m',
                        '???????? ???? system("pause"), ???????? ???????? ???????????? ??????.'], check=True)

        return
    '''
    ### Compilation ###

    compiler_args = ['python3.5', '-m', 'py_compile', CODE_PATH]

    logging.info(' '.join(compiler_args))
    compiler_result = subprocess.run(
        compiler_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    logging.debug('py_compile return code <{}>'.format(compiler_result.returncode))

    if compiler_result.returncode != 0:
        logging.error('Compilation failed!')
        logging.error(compiler_result.stdout)

        subprocess.run(['feedback-result', 'failed'], check=True)
        subprocess.run(['feedback-msg', '-a', '-m',
                        '???????? ???? ??????????/???? ??????????. ???????? ???? ???????? ???????????? ??????.'], check=True)

        if is_staff:
            compiler_msg = subprocess.run(['rst-code', '-c', compiler_result.stdout],
                                          stdout=subprocess.PIPE, check=True).stdout
            compiler_msg = subprocess.run(['rst-msgblock', '-c', 'danger', '-t', 'Compiler Output', '-m', compiler_msg],
                                          check=True, stdout=subprocess.PIPE).stdout
            subprocess.run(['feedback-msg', '-a', '-m', compiler_msg], check=True)

        return

    logging.info('Compilation succeeded!')

    ### Running SNRs ###

    n_snr = 0
    n_success = 0

    # feedback_output_html = ''
    total_scenario_feedback = {}

    logging.debug('Iterating over JSON files')
    for i, snr_path in enumerate(sorted(glob.glob(JSON_PATH + '/*.json'))):

        n_snr += 1

        snr_log_prefix = '[#{}] '.format(i)

        logging.info(snr_log_prefix + 'Running scenario with <{}>'.format(snr_path))

        run_scenario_args = ['run_student', 'bash', 'student/run_scenario.sh', snr_path, str(i)]

        if is_staff:
            run_scenario_args.append('-v5')

        scenario_result = subprocess.run(
            run_scenario_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if scenario_result.returncode in [0, 1, 252, 253]:
            logging.debug(snr_log_prefix + 'No Error in scenario running')

            if scenario_result.returncode in [0, 1]:
                if scenario_result.returncode == 0:
                    logging.info(snr_log_prefix + 'SUCCESS')
                    n_success += 1

                elif scenario_result.returncode == 1:
                    logging.info(snr_log_prefix + 'FAILED')

                scenario_feedback = scenario_result.stdout.decode('utf-8')

                if not scenario_feedback:
                    logging.info(snr_log_prefix + 'Scenario output is empty')
                    raise EmptyScenarioOutputError

            elif scenario_result.returncode in [252, 253]:
                # loading scenario only when needed for saving time
                import scenario

                if scenario_result.returncode == 252:
                    logging.info(snr_log_prefix + 'MEMORY OVERFLOW')
                    scenario_feedback = scenario.api.get_overflow_feedback_json(snr_path)

                elif scenario_result.returncode == 253:
                    logging.info(snr_log_prefix + 'TIMEOUT')
                    scenario_feedback = scenario.api.get_timeout_feedback_json(snr_path)

            logging.debug(snr_log_prefix + 'validating scenario feedback json')
            try:
                scenario_feedback_loaded = json.loads(scenario_feedback)
            except json.JSONDecodeError:
                logging.critical(snr_log_prefix + 'scenario feedback validating failed!')
                raise InvalidScenarioFeedbackJSONError

            logging.debug(snr_log_prefix + 'validating succeeded!')

            scenario_feedback_loaded['prompt'] = SCENARIO_PROMPT

            total_scenario_feedback[i] = scenario_feedback_loaded

        elif scenario_result.returncode in [2, 255, 254]:

            if scenario_result.returncode == 2:
                logging.critical(snr_log_prefix + 'Error in SNR file format')
                raise SNRFileError

            elif scenario_result.returncode == 255:
                logging.critical(snr_log_prefix + 'Error in scenraio program')
                raise ScenarioProgramError

            elif scenario_result.returncode == 245:
                logging.critical(snr_log_prefix + 'Error in INGInious I/O REDIRECT')
                raise INGIniousIORedirectError

        else:
            logging.critical(
                snr_log_prefix + 'Other error in run_scenario.sh <{}>'.format(scenario_result.returncode))

            raise RunScenarioError

    logging.debug('Done iterating over SNR files')

    ### Result & Final Grade ###

    # pass HTML scenario feedback ouput to INGInious
    # taking the total scenario scenarios and injecting the html as a js variable
    # structure is total_scenario_feedback = {"1": json_feedback1, "2": json_feedback2, ...}

    # Dani Rubin changes - 0558858521
    # Changing the response by the data in snr file
    logging.debug('scenario_feedback Updating')
    all_student_tasks = list(sorted(glob.glob(JSON_PATH + '/*.json')))
    
    big_clue_data = ''
    all_clues = ''
    for index, key in enumerate(list(total_scenario_feedback.keys())):
        current_student_file_path = all_student_tasks[index]
        logging.debug('Running over scenerio number - ' + str(key))
        logging.debug('And  scenerio file - ' + current_student_file_path)
        current_text = total_scenario_feedback[key]["feedback"]["text"]
        current_type = total_scenario_feedback[key]["feedback"]["type"]
        logging.debug("The type of error is - " + str(current_type) + " and text - " + str(current_text))

        with open(current_student_file_path) as f:
            file_content = json.load(f)

        if (not str(current_type) == 'None'): 
            error_optional_key = current_type + "_ERROR"
            if(error_optional_key in list(file_content.keys())):
                logging.debug("Found better response. Updating feedback to - " + file_content[error_optional_key])
                total_scenario_feedback[key]["feedback"]["text"] = file_content[error_optional_key]
            else :
                logging.debug("No error like this!")

            if('CLUE' in list(file_content.keys())):
                logging.debug("Found better response. Updating clue to - " + file_content['CLUE'])
                all_clues += file_content['CLUE'] + " <br/> "
            else :
                logging.debug("No CLUE for this!")

        if('MAIN_CLUE' in list(file_content.keys())):
            big_clue_data += file_content['MAIN_CLUE']

    scenario_feedback = u'eval(' + json.dumps(total_scenario_feedback) + u')'

    specific_clue_section = ''
    if (not all_clues == ''):
        specific_clue_section = '<div class="feedback_box" id="code_feedback">' + all_clues + '</div>'



    scenario_output_html = OUTPUT_HTML_PAGE.format(
        feedback_json=scenario_feedback)
    feedback_output_html = '.. raw:: html' + '\n' + indent(scenario_output_html, 4)





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
            "url": "http://localhost:5555/save_data",
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
    $('.feedback-link').click(function() {
        fetch_server_data($(this).attr('data-target'));
    })
    </script>
    '''



    style_section = '''<style>
        .clue_section {
            padding:5px 20px; font-family:sans-serif ;color:#00729A; cursor:pointer; font-size:20px; text-align:right; margin-right:-15px;
        }
        .clue_section:hover {
            border: 1px solid black; padding:4px 19px;
        }
        .solution_section_link {
            padding:5px 20px;font-family:sans-serif ;color:#00729A !important; cursor:pointer; font-size:20px; text-align:right; margin-right:-15px; display:block;text-decoration:none !important;
        }
        .solution_section_link:hover {
            border: 1px solid black;padding:4px 19px;
        }
        #code_clue {
           margin-top:-15px; font-size:16px; text-align:right; display: none; direction:rtl; margin-bottom:20px; margin-right:-15px; padding:15px; background-color: #e7e7e7; border:1px solid #bbb;
        }
        .feedback_box {
           margin-right:-15px;margin-left:15px; font-size:16px; text-align:right; direction:rtl; padding:15px; background-color: #e7e7e7; border:1px solid #bbb;
        }
        #close_clue {
            color: #00729A; cursor: pointer;
        }
    </style>
    '''
    two_parts = feedback_output_html.split('</body>')

    def create_solution():
        def map_taskid_to_solution(taskid):
            split_task = taskid.split('.')
            split_task = list(map(lambda x: "0"+str(x), split_task))
            split_task = '-'.join(split_task)
            return split_task

        logging.debug('Task ID is - ' + taskid)
        return  '''
        <a onclick="fetch_server_data('code_solution')" class="solution_section_link" target="_blank" href="https://s3.eu-west-1.amazonaws.com/data.cyber.org.il/virtual_courses/python/autofeedback/solutions/''' + map_taskid_to_solution(taskid) + '''.py">
            ?????????? ???????????? <span style="font-size:14px">(???????? ?????????? ?????????? ???? ???????? ?????????????? ?????? ???????? ????????!)</span>
        </a><br/>
        '''
        
    def create_clue():
        clue_section = ''
        logging.debug('user name is - ' + username)
        if(not n_snr == n_success):
            if(not big_clue_data == '') :
                clue_section = '''<div class="clue_section"
                    onclick="toggle_sector('code_clue')">
                    ?????? ???????????? 
                </div><br/><div id='code_clue'>''' + big_clue_data + '''<div 
                onclick="toggle_sector('code_clue')" id="close_clue">
                ???????? ???? ????????</div></div>'''
        return clue_section

    casing_section = style_section + toggle_sector 
    
    feedback_output_html = two_parts[0] + casing_section + specific_clue_section + create_clue() + create_solution() + '</body>' + two_parts[1]
    logging.debug(feedback_output_html)





    # TODO - should move to scenario by external api
    # and a check per scenario
    if len(feedback_output_html) > MAX_FEEDBACK_MSG_SIZE:
        logging.info(('feedback_output_html is too big, {} bytes').
                     format(len(feedback_output_html)))

        subprocess.run(['feedback-result', 'failed'], check=True)
        subprocess.run(['feedback-msg', '-a', '-m',
                        '???????????? ???????????? ???????? ?????? ?????? ???????? ???????? ????????????????. ???????? ???? ?????????? ???????????????? ?????????.'],
                       check=True)
        return

    subprocess.run(['feedback-msg', '-a'], stdout=subprocess.PIPE,
                   input=feedback_output_html.encode('utf8'), check=True)

    if n_snr == n_success:
        result = 'success'
        grade = '100'

    else:
        result = 'failed'
        grade = str(int(100 * n_success / n_snr))

    logging.info('++++++++++++++++++++++++++++++')
    logging.info('Result: ' + result)
    logging.info('Grade: ' + str(grade))
    logging.info('++++++++++++++++++++++++++++++')

    subprocess.run(['feedback-result', result], check=True)
    subprocess.run(['feedback-grade', grade], check=True)
    res = subprocess.run(['definetest', 'grade', str(grade)], check=True)

    logging.debug('Done All!')


if __name__ == '__main__':
    try:
        try:
            is_staff = checking_is_staff()
        except Exception as err:
            is_staff = False
            raise err

        main(is_staff)
        sys.exit(0)

    except Exception as err:

        logging.exception('Exception in main! ' + repr(err))

        text = '???????????? ???????? ????????????. ?????? ?????????? ??????. ???? ?????????? ??????????, ?????? ?????? ????????????. '

        if is_staff:
            text += repr(err)
            text += traceback.format_exc()

        subprocess.run(['feedback-result', 'crash'], check=True)
        subprocess.run(['feedback-msg', '-a', '-m', text], check=True)

        sys.exit(-1)


# solution_examples = list(sorted(glob.glob(HTML_PATH + '/*.html')))
#         logging.debug('Searching solution examples. Number of solutions - ' + str(len(solution_examples)))
#         logging.debug('user name is - ' + username)
#         if(len(solution_examples) == 1):
#             with open(solution_examples[0], "r", encoding='utf-8') as f:
#                 file_content= f.read()

#             solution_section = solution_section_start + file_content

#         return solution_section