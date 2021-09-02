from datetime import date, datetime

from flask import abort, Blueprint, flash, redirect, render_template, request

from api.participant_administration import add_fields_and_interventions
from authentication.admin_authentication import (authenticate_researcher_study_access,
    get_researcher_allowed_studies, researcher_is_an_admin)
from config.constants import API_DATE_FORMAT
from database.study_models import Study
from database.user_models import Participant
from libs.push_notification_config import (check_firebase_instance,
    repopulate_all_survey_scheduled_events)

participant_pages = Blueprint('participant_pages', __name__)


@participant_pages.context_processor
def inject_html_params():
    # these variables will be accessible to every template rendering attached to the blueprint
    return {
        "allowed_studies": get_researcher_allowed_studies(),
        "is_admin": researcher_is_an_admin(),
    }


@participant_pages.route('/view_study/<string:study_id>/participant/<string:participant_id>', methods=['GET', 'POST'])
@authenticate_researcher_study_access
def participant(study_id, participant_id):
    try:
        participant = Participant.objects.get(pk=participant_id)
        study = participant.study
    except Participant.DoesNotExist:
        return abort(404)

    # safety check, enforce fields and interventions to be present for both page load and edit.
    add_fields_and_interventions(participant, study)

    if request.method == 'GET':
        return render_participant_page(participant, study)

    # update intervention dates for participant
    for intervention in study.interventions.all():
        input_date = request.values.get(f"intervention{intervention.id}", None)
        intervention_date = participant.intervention_dates.get(intervention=intervention)
        if input_date:
            intervention_date.date = datetime.strptime(input_date, API_DATE_FORMAT).date()
            intervention_date.save()

    # update custom fields dates for participant
    for field in study.fields.all():
        input_id = f"field{field.id}"
        field_value = participant.field_values.get(field=field)
        field_value.value = request.values.get(input_id, None)
        field_value.save()

    # always call through the repopulate everything call, even though we only need to handle
    # relative surveys, the function handles extra cases.
    repopulate_all_survey_scheduled_events(study, participant)

    flash('Successfully edited participant {}.'.format(participant.patient_id), 'success')
    return redirect('/view_study/{:d}/participant/{:d}'.format(study.id, participant.id))


def render_participant_page(participant: Participant, study: Study):
    # to reduce database queries we get all the data across 4 queries and then merge it together.
    # dicts of intervention id to intervention date string, and of field names to value
    # (this was quite slow previously)
    intervention_dates_map = {
        intervention_id:  # this is the intervention's id, not the intervention_date's id.
            intervention_date.strftime(API_DATE_FORMAT) if isinstance(intervention_date, date) else ""
        for intervention_id, intervention_date in
        participant.intervention_dates.values_list("intervention_id", "date")
    }
    participant_fields_map = {
        name: value for name, value in participant.field_values.values_list("field__field_name", "value")
    }

    # list of tuples of (intervention id, intervention name, intervention date)
    intervention_data = [
        (intervention.id, intervention.name, intervention_dates_map.get(intervention.id, ""))
        for intervention in study.interventions.order_by("name")
    ]
    # list of tuples of field name, value.
    field_data = [
        (field_id, field_name, participant_fields_map.get(field_name, ""))
        for field_id, field_name in study.fields.order_by("field_name").values_list('id', "field_name")
    ]

    notification_attempts_count = participant.archived_events.count()
    latest_notification_attempt = \
        get_notification_details(participant.archived_events.order_by('created_on').last(), study.timezone)

    return render_template(
        'participant.html',
        participant=participant,
        study=study,
        intervention_data=intervention_data,
        field_values=field_data,
        notification_attempts_count=notification_attempts_count,
        latest_notification_attempt=latest_notification_attempt,
        push_notifications_enabled_for_ios=check_firebase_instance(require_ios=True),
        push_notifications_enabled_for_android=check_firebase_instance(require_android=True)
    )


def get_notification_details(archived_event, study_timezone):
    # Maybe there's a less janky way to get timezone name, but I don't know what it is:
    timezone_short_name = study_timezone.tzname(datetime.now().astimezone(study_timezone))

    def format_datetime(dt):
        return dt.astimezone(study_timezone).strftime('%A %b %-d, %Y, %-I:%M %p') + " (" + timezone_short_name + ")"

    notification = {}
    if archived_event is not None:
        notification['scheduled_time'] = format_datetime(archived_event.scheduled_time)
        notification['attempted_time'] = format_datetime(archived_event.created_on)
        notification['survey_name'] =\
            ("Audio Survey " if archived_event.survey.survey_type == 'audio_survey' else "Survey ") + \
            archived_event.survey.object_id
        notification['survey_id'] = archived_event.survey.id
        notification['status'] = archived_event.status

    return notification
