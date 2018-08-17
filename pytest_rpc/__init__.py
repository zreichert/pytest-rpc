# -*- coding: utf-8 -*-

__version__ = '0.11.0'

# ======================================================================================================================
# Imports
# ======================================================================================================================
import os
import pytest
import pkg_resources
from datetime import datetime
from zigzag.zigzag import ZigZag


# ======================================================================================================================
# Globals
# ======================================================================================================================
ASC_ENV_VARS = ['BUILD_URL',
                'BUILD_NUMBER',
                'RE_JOB_ACTION',
                'RE_JOB_IMAGE',
                'RE_JOB_SCENARIO',
                'RE_JOB_BRANCH',
                'RPC_RELEASE',
                'RPC_PRODUCT_RELEASE',
                'OS_ARTIFACT_SHA',
                'PYTHON_ARTIFACT_SHA',
                'APT_ARTIFACT_SHA',
                'REPO_URL',
                'JOB_NAME',
                'MOLECULE_TEST_REPO',
                'MOLECULE_SCENARIO_NAME',
                'MOLECULE_GIT_COMMIT']
MK8S_ENV_VARS = ['BUILD_URL',
                 'BUILD_NUMBER',
                 'BUILD_ID',
                 'NODE_NAME',
                 'JOB_NAME',
                 'BUILD_TAG',
                 'JENKINS_URL',
                 'EXECUTOR_NUMBER',
                 'WORKSPACE',
                 'CVS_BRANCH',
                 'GIT_COMMIT',
                 'GIT_URL',
                 'GIT_BRANCH',
                 'GIT_LOCAL_BRANCH',
                 'GIT_AUTHOR_NAME',
                 'GIT_AUTHOR_EMAIL',
                 'BRANCH_NAME',
                 'CHANGE_AUTHOR_DISPLAY_NAME',
                 'CHANGE_AUTHOR',
                 'CHANGE_BRANCH',
                 'CHANGE_FORK',
                 'CHANGE_ID',
                 'CHANGE_TARGET',
                 'CHANGE_TITLE',
                 'CHANGE_URL',
                 'JOB_URL',
                 'NODE_LABELS',
                 'NODE_NAME',
                 'PWD',
                 'STAGE_NAME']


# ======================================================================================================================
# Functions: Private
# ======================================================================================================================
def _capture_marks(items, marks):
    """Add XML properties group to each 'testcase' element that captures the specified marks.

    Args:
        items (list(_pytest.nodes.Item)): List of item objects.
        marks (list(str)): A list of marks to capture and record in JUnitXML for each 'testcase'.
    """

    for item in items:
        for mark in marks:
            marker = item.get_marker(mark)
            if marker is not None:
                for arg in marker.args:
                    item.user_properties.append((mark, arg))


def _get_ci_environment(session):
    """Gets the ci-environment used when executing tests
    default is 'asc'

    Args:
        session (_pytest.main.Session): The pytest session object

    Returns:
        str: The value of the config with the highest precedence
    """
    # Determine if the option passed with the highest precedence is a valid option
    highest_precedence = _get_option_of_highest_precedence(session, 'ci-environment') or 'asc'
    white_list = ['asc', 'mk8s']
    if not any(x == highest_precedence for x in white_list):
        raise RuntimeError(
            "The value {} is not a valid value for the 'ci-environment' configuration".format(highest_precedence))

    return highest_precedence


def _get_option_of_highest_precedence(session, option_name):
    """looks in the session and returns the option of the highest precedence
    This assumes that there are options and flags that are equivalent

    Args:
        session (_pytest.main.Session): The pytest session object
        option_name (str): The name of the option

    Returns:
        str: The value of the option that is of highest precedence
        None: no value is present
    """
    #  Try to get configs from CLI and ini
    try:
        cli_option = session.config.getoption("--{}".format(option_name))
    except ValueError:
        cli_option = None
    try:
        ini_option = session.config.getini(option_name)
    except ValueError:
        ini_option = None
    highest_precedence = cli_option or ini_option
    return highest_precedence


# ======================================================================================================================
# Functions: Public
# ======================================================================================================================
@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus, terminalreporter):
    """This hook is used by pytest to build the junit XML
    Using ZigZag as a library we upload in the pytest runtime

    Args:
        session (_pytest.main.Session): The pytest session object
        exitstatus
    """
    if session.config.pluginmanager.hasplugin('junitxml'):
        if _get_option_of_highest_precedence(session, 'zigzag'):
            qtest_project_id = _get_option_of_highest_precedence(session, 'qtest-project-id')
            if qtest_project_id:
                junit_file_path = getattr(session.config, '_xml', None).logfile
                if junit_file_path:  # extra test to make double sure we have a file path recommended by Ryan
                    try:
                        zz = ZigZag(junit_file_path,
                                    os.environ['QTEST_API_TOKEN'],
                                    qtest_project_id,
                                    qtest_test_cycle,
                                    pprint_on_fail)
                        zz.upload_test_results()
                        # we should print the status of our upload attempt
                    except Exception as e: # we want this super broad so we dont break test execution
                        pass # TODO print the exception and continue


@pytest.hookimpl(tryfirst=True)
def pytest_runtestloop(session):
    """Add XML properties group to the 'testsuite' element that captures the values for specified environment variables.

    Args:
        session (_pytest.main.Session): The pytest session object
    """

    if session.config.pluginmanager.hasplugin('junitxml'):
            junit_xml_config = getattr(session.config, '_xml', None)

            if junit_xml_config:
                ci_environment = \
                    _get_ci_environment(session)
                junit_xml_config.add_global_property('ci-environment', ci_environment)
                if ci_environment == 'asc':
                    for env_var in ASC_ENV_VARS:
                        junit_xml_config.add_global_property(env_var, os.getenv(env_var, 'Unknown'))
                elif ci_environment == 'mk8s':
                    for env_var in MK8S_ENV_VARS:
                        junit_xml_config.add_global_property(env_var, os.getenv(env_var, 'Unknown'))


def pytest_collection_modifyitems(items):
    """Called after collection has been performed, may filter or re-order the items in-place.

    Args:
        items (list(_pytest.nodes.Item)): List of item objects.
    """

    _capture_marks(items, ('test_id', 'jira'))


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Add XML properties group to the 'testcase' element that captures start time in UTC.

    Args:
        item (_pytest.nodes.Item): An item object.
    """
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    item.user_properties.append(('start_time', now))


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item):
    """Add XML properties group to the 'testcase' element that captures start time in UTC.

    Args:
        item (_pytest.nodes.Item): An item object.
    """
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    item.user_properties.append(('end_time', now))


def pytest_addoption(parser):
    """Adds a config option to pytest

    Args:
        parser (_pytest.config.Parser): A parser object
    """
    config_option = "ci-environment"
    config_option_help = "The ci-environment used to execute the tests, (default: 'asc')"
    parser.addini(config_option, config_option_help)
    parser.addoption("--{}".format(config_option), help=config_option_help)

    # options related to publishing
    zigzag_help = 'Tell pytest to automatically publish with ZigZag'
    parser.addini('zigzag', zigzag_help, type=bool, default=False)
    parser.addoption('--zigzag', zigzag_help, type=bool, default=False)

    project_help = 'The project ID you would like zigzag to use on upload'
    parser.addini('qtest-project-id', project_help, type=bool, default=False)
    parser.addoption('--qtest-project-id', project_help, type=bool, default=False)


def get_xsd(ci_environment='asc'):
    """Retrieve a XSD for validating JUnitXML results produced by this plug-in.

    Args:
        ci_environment (str): the value found in the ci-environment global property from the XML

    Returns:
        io.BytesIO: A file like stream object.
    """

    if ci_environment == 'asc':
        return pkg_resources.resource_stream('pytest_rpc', 'data/molecule_junit.xsd')
    elif ci_environment == 'mk8s':
        return pkg_resources.resource_stream('pytest_rpc', 'data/mk8s_junit.xsd')
    else:
        raise RuntimeError("Unknown ci-environment '{}'".format(ci_environment))
