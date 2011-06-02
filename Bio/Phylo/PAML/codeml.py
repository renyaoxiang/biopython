# Copyright (C) 2011 by Brandon Invergo (b.invergo@gmail.com)
# This code is part of the Biopython distribution and governed by its
# license. Please see the LICENSE file that should have been included
# as part of this package.

from __future__ import with_statement
import os
import os.path
import re
from _paml import Paml, PamlError
import _parse_codeml

class CodemlError(EnvironmentError):
    """CODEML has failed. Run with verbose = True to view CODEML's error
message"""

class Codeml(Paml):
    """This class implements an interface to CODEML, part of the PAML package."""

    def __init__(self, alignment = None, tree = None, working_dir = None,
                out_file = None):
        """Initialize the codeml instance. 
        
        The user may optionally pass in strings specifying the locations
        of the input alignment and tree files, the working directory and
        the final output file. Other options found in the CODEML control
        have typical settings by default to run site class models 0, 1 and
        2 on a nucleotide alignment.
        """
        Paml.__init__(self, alignment, working_dir, out_file)
        if tree is not None:
            if not os.path.exists(tree):
                raise IOError, "The specified tree file does not exist."
        self.tree = tree
        self.ctl_file = "codeml.ctl"
        self._options = {"noisy": 9, 
                        "verbose": 1, 
                        "runmode": 0,
                        "seqtype": 2, 
                        "CodonFreq": 2, 
                        "ndata": None,
                        "clock": 0, 
                        "aaDist": 0,
                        "aaRatefile": "dat/jones.dat", 
                        "model": 2,
                        "NSsites": [0], 
                        "icode": 0, 
                        "Mgene": 0,
                        "fix_kappa": 0, 
                        "kappa": 2, 
                        "fix_omega": 0,
                        "omega": .4, 
                        "fix_alpha": 1, 
                        "alpha": 0,
                        "Malpha": 0, 
                        "ncatG": 8, 
                        "getSE": 0,
                        "RateAncestor": 1, 
                        "Small_Diff": .5e-6,
                        "cleandata": 1, 
                        "fix_blength": None, 
                        "method": 0}
                        
    def write_ctl_file(self):
        """Dynamically build a CODEML control file from the options.
        
        The control file is written to the location specified by the 
        ctl_file property of the codeml class.
        """
        # Make sure all paths are relative to the working directory
        try:
            self._set_rel_paths()
        except (AttributeError, ValueError) as error:
            raise error
        with open(self.ctl_file, 'w') as ctl_handle:
            ctl_handle.write("seqfile = {0}\n".format(self._rel_alignment))
            ctl_handle.write("outfile = {0}\n".format(self._rel_out_file))
            ctl_handle.write("treefile = {0}\n".format(self._rel_tree))
            for option in self._options.items():
                if option[1] == None:
                    # If an option has a value of None, there's no need
                    # to write it in the control file; it's normally just
                    # commented out.
                    continue
                if option[0] == "NSsites":
                    # NSsites is stored in Python as a list but in the 
                    # control file it is specified as a series of numbers
                    # separated by spaces.
                    NSsites = " ".join(["{0}".format(site) for site in option[1]])
                    ctl_handle.write("{0} = {1}\n".format(option[0], NSsites))
                else:
                    ctl_handle.write("{0} = {1}\n".format(option[0], 
                        option[1]))
    
    def read_ctl_file(self, ctl_file):
        """Parse a control file and load the options into the Codeml instance.
        """
        temp_options = {}
        with open(ctl_file) as ctl_handle:
            for line in ctl_handle:
                line = line.strip()
                uncommented = line.partition("*")[0]
                if uncommented != "":
                    if "=" not in uncommented:
                        raise AttributeError, \
                            "Malformed line in control file:\n{0}".format(line)
                    (option, value) = uncommented.split("=")
                    option = option.strip()
                    value = value.strip()
                    if option == "seqfile":
                        self.alignment = value
                    elif option == "treefile":
                        self.tree = value
                    elif option == "outfile":
                        self.out_file = value
                    elif option == "NSsites":
                        site_classes = value.split(" ")
                        for n in range(len(site_classes)):
                            try:
                                site_classes[n] = int(site_classes[n])
                            except:
                                raise TypeError, \
                                    "Invalid site class: {0}".format(site_classes[n])
                        temp_options["NSsites"] = site_classes
                    elif option not in self._options:
                        raise KeyError, "Invalid option: {0}".format(option)
                    else:
                        if "." in value:
                            try:
                                converted_value = float(value)
                            except:
                                converted_value = value
                        else:
                            try:
                                converted_value = int(value)
                            except:
                                converted_value = value
                        temp_options[option] = converted_value
        for option in self._options.keys():
            if option in temp_options.keys():
                self._options[option] = temp_options[option]
            else:
                self._options[option] = None
                            
    def print_options(self):
        """Print out all of the options and their current settings."""
        for option in self._options.items():
            if option[0] == "NSsites":
                # NSsites is stored in Python as a list but in the 
                # control file it is specified as a series of numbers
                # separated by spaces.
                NSsites = " ".join(["{0}".format(site) for site in option[1]])
                print "{0} = {1}".format(option[0], NSsites)
            else:
                print "{0} = {1}".format(option[0], option[1])
        
    def _set_rel_paths(self):
        """Convert all file/directory locations to paths relative to the current working directory.
        
        CODEML requires that all paths specified in the control file be
        relative to the directory from which it is called rather than 
        absolute paths.
        """
        Paml._set_rel_paths(self)
        if self.tree is not None:
            self._rel_tree = os.path.relpath(self.tree, 
                self.working_dir)
        
    def run(self, ctl_file = None, verbose = False, command = "codeml",
                parse = True):
        """Run codeml using the current configuration and then parse the results. 
        
        Return a process signal so the user can determine if
        the execution was successful (return code 0 is successful, -N
        indicates a failure). The arguments may be passed as either 
        absolute or relative paths, despite the fact that CODEML 
        requires relative paths.
        """
        if self.tree is None:
            raise ValueError, "Tree file not specified."
        if not os.path.exists(self.tree):
            raise IOError, "The specified tree file does not exist."
        try:
            Paml.run(self, ctl_file, verbose, command)
        except PamlError as strerror:
            raise PamlError, strerror
        if parse:
            try:
                results = read(self._rel_out_file)
            except KeyError as (errorno, strerror):
                raise KeyError, strerror
            except ValueError as (errorno, strerror):
                raise ValueError, strerror
        else:
            results = None
        return results        

def read(results_file):
    """Parse a CODEML results file."""
    results = {}
    if not os.path.exists(results_file):
        raise IOError, "Results file does not exist."
    with open(results_file) as results_handle:
        lines = results_handle.readlines()
    multi_models = _parse_codeml.parse_basics(lines, results)
    _parse_codeml.parse_nssites(lines, results, multi_models)
    _parse_codeml.parse_pairwise(lines, results)
    _parse_codeml.parse_distances(lines, results)
    if len(results) == 0:
        raise ValueError, "Invalid results file"
    return results
