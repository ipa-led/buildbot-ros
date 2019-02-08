from buildbot.config import BuilderConfig
from buildbot.changes.gitpoller import GitPoller
from buildbot.plugins import util, schedulers
from buildbot.process.factory import BuildFactory
from buildbot.process.properties import Interpolate
from buildbot.process import results
from buildbot.steps.source.git import Git
from buildbot.steps.shell import ShellCommand
from buildbot.steps.transfer import FileDownload

from buildbot_ros_cfg.helpers import success
from buildbot_ros_cfg.git_pr_poller import GitPRPoller


## @brief Testbuild jobs are used for CI testing of the source repo.
## @param c The Buildmasterconfig
## @param job_name Name for this job (typically the metapackage name)
## @param url URL of the SOURCE repository.
## @param branch Branch to checkout.
## @param distro Ubuntu distro to build for (for instance, 'precise')
## @param arch Architecture to build for (for instance, 'amd64')
## @param rosdistro ROS distro (for instance, 'groovy')
## @param machines List of machines this can build on.
## @param othermirror Cowbuilder othermirror parameter
## @param keys List of keys that cowbuilder will need
def ros_testbuild(c, job_name, url, branch, distro, arch, rosdistro, machines, 
                  othermirror, keys, source=True, locks=[]):

    # Create a Job for Source
    
    if source:
        project_name = '_'.join([job_name, rosdistro, 'testbuild'])
        c['change_source'].append(
            GitPoller(
                repourl=url,
                name=url,
                branch=branch,
                category=project_name,
                pollAtLaunch=True,
            )
        )
        c['schedulers'].append(
            schedulers.SingleBranchScheduler(
                name=project_name,
                builderNames=[project_name,],
                change_filter=util.ChangeFilter(category=project_name)
            )  
        )
    else:
        r_owner, r_name = (url.split(':')[1])[:-4].split('/')
        project_name = '_'.join([job_name, rosdistro, 'pr_testbuild'])
        c['change_source'].append(
            GitPRPoller(
                owner=r_owner,
                repo=r_name,
                category=project_name,
                branches=[branch],
                pollInterval=10*60,
                pollAtLaunch=True,
                token=util.Secret("OathToken"),
                repository_type='ssh'
            )
        )

        c['schedulers'].append(
            schedulers.SingleBranchScheduler(
                name=project_name,
                builderNames=[project_name,],
                change_filter=util.ChangeFilter(category=project_name)
            )
        )
        
    # Directory which will be bind-mounted
    binddir = '/tmp/'+project_name
    

    f = BuildFactory()
    # Remove any old crud in /tmp folder
    f.addStep(
        ShellCommand(
            command=['rm', '-rf', binddir],
            hideStepIf=success
        )
    )
    # Check out repository (to /tmp)
    f.addStep(
        Git(
            repourl=util.Property('repository', default=url),
            branch=util.Property('branch', default=branch),
            alwaysUseLatest=True,
            mode='full',
            workdir=binddir+'/src/'+job_name
        )
    )
    # Download testbuild.py script from master
    f.addStep(
        FileDownload(
            name=job_name+'-grab-script',
            mastersrc='scripts/testbuild.py',
            workerdest=Interpolate('%(prop:builddir)s/testbuild.py'),
            hideStepIf=success
        )
    )
    # Update the cowbuilder
    f.addStep(
        ShellCommand(
            command=['cowbuilder-update.py', distro, arch] + keys,
            hideStepIf=success
        )
    )
    # Make and run tests in a cowbuilder
    f.addStep(
        ShellCommand(
            name=job_name+'-build',
            command=['sudo', 'cowbuilder', '--execute',
                     Interpolate('%(prop:builddir)s/testbuild.py'),
                     '--distribution', distro, '--architecture', arch,
                     '--bindmounts', binddir, '--basepath',
                     '/var/cache/pbuilder/base-'+distro+'-'+arch+'.cow',
                     '--override-config', '--othermirror', othermirror,
                     '--', binddir, rosdistro],
            logfiles={'tests' : binddir+'/testresults'},
            descriptionDone=['make and test', job_name]
        )
    )
    c['builders'].append(
        BuilderConfig(
            name=project_name,
            workernames=machines,
            factory=f,
            locks=locks
        )
    )
    # return the name of the job created
    return project_name



## @brief ShellCommand w/overloaded evaluateCommand so that tests can be Warn
class TestBuild(ShellCommand):
    warnOnWarnings = True

    def evaluateCommand(self, cmd):
        
        if cmd.didFail():
            # build failed
            return results.FAILURE

        l = self.getLog('tests').readlines()
        if len(l) >= 1:
            if l[0].find('Passed') > -1:
                return results.SUCCESS
            else:
                # some tests failed
                return results.WARNINGS
