import json
from datetime import timedelta
from typing import List

from celery import Celery
from django.utils import timezone
from kombu.exceptions import OperationalError

from constants.celery_constants import (CELERY_CONFIG_LOCATION, DATA_PROCESSING_CELERY_SERVICE,
    FOREST_SERVICE, PUSH_NOTIFICATION_SEND_SERVICE)


def safe_apply_async(a_task_for_a_celery_queue, *args, **kwargs):
    """ Enqueuing a new task, for which we use Celery's most flexible `apply_async` function,
    can fail deep inside amqp/transport.py with an OperationalError. Use this common wrapper to
    handle that case.

    An "a_task_for_a_celery_queue" is either a "@celery_app.task"-wrapped function' or it is a
    FalseCeleryApp. FalseCeleryApps implement an apply_async passthrough function that allows us to
    test "celery code" in the terminal. In the terminal everything is perfectly sequential and easy,
    without and devs don't need an active celery instance. """
    for i in range(10):
        try:
            return a_task_for_a_celery_queue.apply_async(*args, **kwargs)
        except OperationalError:
            # after 4+ years in production this strategy works perfectly.  Cool.
            if i >= 3:
                raise


#
# Helper classes
#

class FalseCeleryAppError(Exception): pass
class CeleryNotRunningException(Exception): pass


class FalseCeleryApp:
    """ Class that mimics enough functionality of a Celery app for us to be able to execute
    our celery infrastructure from the shell, single-threaded, without queuing. """
    
    def __init__(self, an_function: callable):
        """ at instantiation (aka when used as a decorator) stash the function we wrap """
        print(f"Instantiating a FalseCeleryApp for {an_function.__name__}.")
        self.an_function = an_function
    
    @staticmethod
    def task(*args, **kwargs):
        """ Our pattern is that we wrap our celery functions in the task decorator.
        This function executes at-import-time because it is a file-global function declaration with
        a celery_app.task(queue=queue_name) decorator. Our hack is to declare a static "task" method
        that does nothing but returns a FalseCelery app. """
        print(f"task declared, args: {args}, kwargs:{kwargs}")
        return FalseCeleryApp
    
    def apply_async(self, *args, **kwargs):
        """ apply_async is the function we use to queue up tasks.  Our hack is to declare
        our own apply_async function that extracts the "args" parameter.  We pass those
        into our stored function. """
        print(f"apply_async running, args:{args}, kwargs:{kwargs}")
        if "args" not in kwargs:
            raise FalseCeleryAppError("'args' was not present?")
        return self.an_function(*kwargs["args"])


#
# Connections to Celery (or FalseCeleryApps if Celery is not present)
#

FORCE_CELERY_OFF = False


def instantiate_celery_app_connection(service_name: str) -> Celery or FalseCeleryApp:
    # this isn't viable because it breaks watch_processing (etc), because the celery.task.inspect
    # call will time out if no Celery object has been instantiated with credentials.
    # if RUNNING_TEST_OR_IN_A_SHELL:
    # return FalseCeleryApp
    
    if FORCE_CELERY_OFF:
        return FalseCeleryApp
    
    # the location of the manager_ip credentials file is in the folder above the project folder.
    try:
        with open(CELERY_CONFIG_LOCATION, 'r') as f:
            manager_ip, password = f.read().splitlines()
    except IOError:
        return FalseCeleryApp
    
    return Celery(
        service_name,
        # note that the 2nd trailing slash here is required, it is some default rabbitmq thing.
        broker=f'pyamqp://beiwe:{password}@{manager_ip}//',  # the pyamqp_endpoint.
        backend='rpc://',
        task_publish_retry=False,
        task_track_started=True,
    )


# if None then there is no celery app.
processing_celery_app = instantiate_celery_app_connection(DATA_PROCESSING_CELERY_SERVICE)
push_send_celery_app = instantiate_celery_app_connection(PUSH_NOTIFICATION_SEND_SERVICE)
forest_celery_app = instantiate_celery_app_connection(FOREST_SERVICE)


#
# The remaining functions are helpers for use in a live shell session on a machine running celery.
# All return a list of ids (can be empty), or None if celery isn't currently running.
#

def inspect():
    """ Inspect is annoyingly unreliable and has a default 1 second timeout.
        Will error if executed while a FalseCeleryApp is in use. """
    
    # this function intentionally breaks if you every instantiated a false celery app
    if (
        isinstance(processing_celery_app, FalseCeleryApp)
        or isinstance(push_send_celery_app, FalseCeleryApp)
        or isinstance(forest_celery_app, FalseCeleryApp)
    ):
        raise CeleryNotRunningException("FalseCeleryApp is in use, this session is not connected to celery.")
    
    # this import needs to come after the celery app is loaded, the class is dynamic
    # and the inspect function is injected, it is not present in the source.
    from celery.task.control import inspect as celery_inspect
    now = timezone.now()
    fail_time = now + timedelta(seconds=20)
    
    while now < fail_time:
        try:
            return celery_inspect(timeout=0.1)
        except CeleryNotRunningException:
            now = timezone.now()
            continue
    
    raise CeleryNotRunningException()


# TODO: where are these string parameters from? Need to instantiate one for Forest. (Probably)

def get_notification_scheduled_job_ids() -> List[int] or None:
    return _get_job_ids(inspect().scheduled(), "notifications")
def get_notification_reserved_job_ids() -> List[int] or None:
    return _get_job_ids(inspect().reserved(), "notifications")
def get_notification_active_job_ids() -> List[int] or None:
    return _get_job_ids(inspect().active(), "notifications")

# Processing
def get_processing_scheduled_job_ids() -> List[int] or None:
    return _get_job_ids(inspect().scheduled(), "processing")
def get_processing_reserved_job_ids() -> List[int] or None:
    return _get_job_ids(inspect().reserved(), "processing")
def get_processing_active_job_ids() -> List[int] or None:
    return _get_job_ids(inspect().active(), "processing")


def get_revoked_job_ids():
    """ Returns a list of a tuple of two lists of usually ints. """
    return list(inspect().revoked().values())


def _get_job_ids(celery_query_dict, celery_app_suffix):
    """ This is a utility function for poking live celery apps.

    Data structure looks like this, we just want that args component.
    Returns list of ids (can be empty), or None if celery isn't currently running.

    {'celery@ip-172-31-78-176': [{'id': '12e579ee-c603-4f06-b80c-dd78c330e539',
       'name': 'services.celery_data_processing.queue_user',
       'args': '[7235]',
       'kwargs': '{}',
       'type': 'services.celery_data_processing.queue_user',
       'hostname': 'celery@ip-172-31-78-176',
       'time_start': 2387953.778238536,
       'acknowledged': True,
       'delivery_info': {'exchange': '',
        'routing_key': 'celery',
        'priority': 0,
        'redelivered': False},
       'worker_pid': 27291},
        {'id': 'd49aad01-2392-4607-91f7-5f9416a9941f',
         'name': 'services.celery_data_processing.queue_user',
         'args': '[7501]',
         'kwargs': '{}',
         'type': 'services.celery_data_processing.queue_user',
         'hostname': 'celery@ip-172-31-78-176',
         'time_start': 2387939.015288787,
         'acknowledged': True,
         'delivery_info': {'exchange': '',
          'routing_key': 'celery',
          'priority': 0,
          'redelivered': False},
         'worker_pid': 27292}]}
    """
    
    # for when celery isn't running
    if celery_query_dict is None:
        raise CeleryNotRunningException()
    
    # below could be substantially improved. itertools chain....
    all_processing_jobs = []
    for worker_name, list_of_jobs in celery_query_dict.items():
        if worker_name.endswith(celery_app_suffix):
            all_processing_jobs.extend(list_of_jobs)
    
    all_args = []
    for job_arg in [job['args'] for job in all_processing_jobs]:
        # 2020-11-24:: this job_arg value has started to return a list object, not a json string
        #  ... but only on one of 3 newly updated servers. ...  Buh?
        args = job_arg if isinstance(job_arg, list) else json.loads(job_arg)
        # safety/sanity check, assert that there is only 1 integer id in a list and that it is a list.
        assert isinstance(args, list)
        assert len(args) == 1
        assert isinstance(args[0], int)
        all_args.append(args[0])
    
    return all_args
