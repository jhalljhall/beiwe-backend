from datetime import datetime
from flask import Blueprint, request, jsonify, render_template
from libs.admin_authentication import authenticate_admin
from libs.s3 import (s3_list_files, s3_retrieve, s3_upload_handler_string,
                     s3_copy_with_new_name)


survey_designer = Blueprint('survey_designer', __name__)

################################################################################
############################### Setters ########################################
################################################################################

# TODO: Josh. make sure that uncommenting @authenticate_admin
# does not break survey editing.

@survey_designer.route('/update_survey', methods=['GET', 'POST'])
# @authenticate_admin
def update_daily():
    return update_survey("current_survey")
    #return update_survey("daily", request)


#TODO: Josh.  make sure the weekly and daily surveys edit their respective surveys.
    #(this function is never called...)
# @survey_designer.route('/update_survey', methods=['GET', 'POST'])
# @authenticate_admin
# def update_weekly():
#     return update_survey("weekly", request)


def update_survey(survey_name):
    survey_name = "all_surveys/" + survey_name
    #TODO: Josh. stick in the identifier for the field(?) to grab from the post request.
    # you will probably need to write the post request before you can answer this question.
    new_quiz = request.values['JSONstring']
    print 'JSONstring = ' + new_quiz
    if (len(s3_list_files( survey_name )) > 0) :
        old_survey_new_name = survey_name + datetime.now().isoformat()
        s3_copy_with_new_name( survey_name, old_survey_new_name )
    s3_upload_handler_string( survey_name, new_quiz )
    # TODO: Josh, only return 200 on success; otherwise something else
    # TODO: Josh, Javascript that pulls the survey from the server should now pull it from "all_surveys/current_survey"
    return '200'


################################################################################
############################### Getters ########################################
################################################################################

def get_surveys(prefix="survey/"):
    surveys = s3_list_files(prefix)
    return [i.strip(prefix).strip(".json") for i in surveys]


def get_latest_weekly():
    """ Method responsible for fetching latest created weekly survey
        (frequency 1) """
    weeklies = get_surveys("survey/weekly/")
    weeklies = sorted(weeklies, reverse=True)
    return jsonify(s3_retrieve(weeklies[0]))


def get_latest_daily():
    """ Method responsible for fetching latest created daily survey (frequency 1) """
    dailies = get_surveys("survey/daily/")
    dailies = sorted(dailies, reverse=True)
    return jsonify(s3_retrieve(dailies[0]))


################################################################################
########################### Pure routes ########################################
################################################################################

@survey_designer.route('/survey_designer')
@authenticate_admin
def render_survey_builder():
    data = {}
    return render_template('survey_designer.html', data)

@survey_designer.route('/surveys')
@authenticate_admin
def render_surveys():
    data = {}
    return render_template('surveys.html', data)

@survey_designer.route('/survey_designer')
@authenticate_admin
def render_survey_designer():
    return render_template('survey_designer.html')

@survey_designer.route('/question_designer')
@authenticate_admin
def question_designer():
    return render_template('question_designer.html')

@survey_designer.route('/weekly_survey')
@authenticate_admin
def weekly_survey():
    return render_template('weekly_survey.html')

@survey_designer.route('/daily_survey')
@authenticate_admin
def daily_survey():
    return render_template('daily_survey.html')