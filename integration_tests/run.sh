#!/bin/bash
# script for jenkins to run tests on polar2grid

cd "$WORKSPACE"
mkdir -p integration_tests/jenkins_p2g_env

# environment already has polar2grid installed on it
tar -xzf /data/users/kkolman/integration_tests/polar2grid/integration_tests/jenkins_p2g_env.tar.gz -C $WORKSPACE/integration_tests/jenkins_p2g_env
source integration_tests/jenkins_p2g_env/bin/activate
./create_software_bundle.sh test_swbundle
export POLAR2GRID_HOME="$WORKSPACE/test_swbundle"
cd "$WORKSPACE/integration_tests"
behave --no-logcapture --no-color --no-capture -D datapath=/data/users/kkolman/integration_tests/polar2grid/integration_tests/p2g_test_data
exit $?
