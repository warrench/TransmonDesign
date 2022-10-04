"""
Models the decoherence of a transmon using Fermis golden rule

Or other design rules

@author: Christopher Warren (Chalmers University of Technology)
@date: 2020
"""

import numpy as np


def Gamma_rel(omega, D_trans, S, args=None):
    return (np.pi/2)*(D_trans**2)*S(omega, *args)

def Gamma_phi(omega, D_phi, S, args=None):
    return (np.pi)*(D_phi**2)*S(0, *args)