Release Notes
=============

Mini-NDN version 0.6.0 (Major changes since version 0.5.0)
----------------------------------------------------------

**Breaking Changes**:

- Rewrite install script (`issue: 4630 <https://redmine.named-data.net/issues/4630>`__)

  -  Set dependency versions: PPA, git repository & commit
  -  Separate download and build+install steps
  -  Don't reinstall package if it's already installed
  -  More details `here <https://github.com/named-data/mini-ndn/blob/master/docs/install.rst>`__

- `Note: <https://redmine.named-data.net/issues/5161>`__ We have dropped support for python 2, the latest Mini-NDN requires at least python 3.0

**New features**:

-  Update Mini-NDN codebase with Mini-NDN-Wifi code (`issue: 4858 <https://redmine.named-data.net/issues/4858>`__)

-  Provide pre-built Mini-NDN Vagrant box and Docker container

-  Added several new examples:

  - consumer/producer
  - ndnping
  - traffic generator
  - catchunks/putchunks

- Allow for creation of net object without topology (`issue: 5162 <https://redmine.named-data.net/issues/5162>`__)

**Improvements and Bug Fixes**:

-  Support running NDN applications on mixed topologies (`issue: 5160 <https://redmine.named-data.net/issues/5160>`__)

-  Support route addition using face-id in `Nfdc` helper (`issue: 5130 <https://redmine.named-data.net/issues/5130>`__)

-  Add wrapper for `ndnpingserver` and fix passing the Mininet host object as a prefix on ndnpingclient

-  Show status of route calculation in `NdnRoutingHelper`

-  Incorporate changes of `NDNPing` Class (wrapper of pingserver and pingclient) in the examples

-  Support simple topology files with no additional parameters


Mini-NDN version 0.5.0 (Major changes since version 0.4.0)
----------------------------------------------------------

**Breaking Changes**:

-  `Mini-NDN re-design <https://redmine.named-data.net/issues/5062>`__: simple and robust design with better quality, control, and more consistency with Mininet

**New features**:

-  Add a script to generate up-to-date NDN testbed topologies for Mini-NDN

-  Add Mini-NDN utility application for PCAP logging

-  Add NDN routing helper to compute centralized LS and HR routes

-  Add routing helper to allow IP communication in experiments

-  Add startup experiments for NLSR and current testbed topology

-  Move the NDNPing wrapper method to a helper class

-  Create a helper class to provide a wrapper around ``nfdc``

**Improvements and Bug Fixes**:

-  Change workDir and resultDir to be class attribute

-  Quiet apt install for Vagrant

-  Fix route computation bug in ``ndn_routing_helper``

-  Fix overwriting of existing prefixes in ``ndn_routing_helper``

-  Move log files to resultDir after evaluation finishes

-  Check for duplicate HR coordinates in the topology file

-  Check PSync integration and add a tests case for it

-  Bug fixes in nfdc and experiments

-  Added functionality to check Mini-NDN dependencies

-  Parser fix to avoid an infinite loop

-  Allow use of NFD and NLSR PPA with Mini-NDN

-  Remove arbitrary arguments in favor of parsing arguments from experiment files

-  Auto-complete command-line arguments

-  Add option to set CS size

-  Adjust to use ndn-cxx logging


Mini-NDN version 0.4.0 (changes since version 0.3.0)
----------------------------------------------------

Release date: January 10, 2018

**New features**:

-  Use SIGQUIT to quit Mini-NDN, SIGINT to kill programs

-  Use Infoedit to edit NFD and NLSR configuration files

-  Use nlsr.conf installed in the system

-  Provide a Vagrantfile to setup Mini-NDN and NDN

-  Provide option to disable NLSR

-  Provide an option to run NLSR in dry-run mode

-  Add option to specify whether to use TCP or UDP face in nlsr.conf

-  Add option to specify arbitrary arguments to use in experiments

-  Include a single option to install Mini-NDN and all the dependencies

**Bug fixes**:

-  Fix "key does not exist error" after NLSR starts

-  Update install.sh to call ldconfig after installing ChronoSync

-  Add hyperbolic coordinates to default topology

**Misc changes**:

-  Add an experiment to test nlsrc

-  Create faces in NFD for each neighbor in NLSR

-  Update to latest ndn-cxx

-  Use /tmp/minindn folder as default work dir instead of /tmp

Mini-NDN version 0.3.0 (changes since version 0.2.0)
----------------------------------------------------

Release date: March 3, 2017

**New features**:

-  Mini-NDN cluster edition

-  New experiments for making NLSR testing easier

**Bug fixes**:

-  Set site name correctly

-  Install missing certificates in NLSR security config

-  Fix quitting of NLSR due to key not found error

**Misc changes**:

-  Removed nlsr.conf file, generate it within the code

-  Use argparse instead of deprecated optparse

-  Update security config section for NLSR

-  Change mininet prompt to mini-ndn

-  Set network name at one place

-  Update install.sh script to install openssl

-  Update install.sh script to install cryptopp from package instead of
   compiling from source

-  Update install.sh to clean build folder every time to get rid of
   removed files such as old experiments

-  Fix old code - use net.hosts instead of storing hosts in a variable

-  Use nfdc instead of deprecated nfd-status

Mini-NDN version 0.2.0 (changes since version 0.1.1)
----------------------------------------------------

Release date: August 18, 2016

**New features**:

-  Automatic security configuration for NLSR

-  Use /usr/local/etc/ndn/nfd.conf as default config file for NFD

-  Class to monitor /proc/$PID/stat file for PID

-  Mini-NDN exits gracefully on SIGINT and non-convergence

-  Faster Mini-NDN install script - does not do apt-get update everytime

-  NLSR is launched with explicit config file for easier process
   identification

-  Add and update more documentation

**Bug fixes**:

-  NFD is killed correctly on exit

-  Best route strategy is set correctly

Mini-NDN version 0.1.1 (changes since version 0.1.0)
----------------------------------------------------

Release date: November 4, 2015

**New features**:

-  Use nfd.conf.sample from currently installed NFD

-  Add working directory option to allow execution environment outside
   of /tmp

-  Add results directory option to store experiment results after
   completion

-  Add support for switches in GUI and configuration file

-  Add failNode and recoverNode methods to Experiment class

-  Add most connected node (MCN) failure experiment

-  Add option to specify percentage of nodes pinged

**Code changes**:

-  Refactor program options into container class

-  Remove unused "FIB Entries" option from NDN host options

**Bug fixes**:

-  Abort start up if experiment name is invalid

-  Restart pings after recovery in failure experiment

Mini-NDN version 0.1.0 (initial release)
----------------------------------------

Release date: July 15, 2015

Mini-NDN is a lightweight networking emulation tool that enables
testing, experimentation, and research on the NDN platform. Based on
Mininet, Mini-NDN uses the NDN libraries, NFD, NLSR, and tools released
by the `NDN project <http://named-data.net/codebase/platform/>`__ to
emulate an NDN network on a single system.

**Included features**:

-  Run a complete NDN network on a single system

-  Automatic configuration of NLSR to provide a routable NDN network

-  Supports user created NDN applications

-  Create a topology using the included Mini-NDN Edit GUI application

-  Allows individual configuration of NFD and NLSR parameters for each
   node

-  Provides an experiment management framework for easy creation of
   custom networking experiments

-  Uses a simple topology file format to define hosts, links, and
   configuration values

-  Configure network link parameters including bandwidth, delay, and
   loss rate

-  Includes a pre-configured topology file to replicate the NDN testbed
