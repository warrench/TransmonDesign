"""
Models the Transmon qubit closer to the analytic solution than
the Duffing oscillator model. Can work backwards from target qubit
parameters to get the Ej, Ec or use input Ej, Ec to find the spectrum
of the Cooper Pair Box.

@author: Christopher Warren (Chalmers University of Technology)
@date: 2020
"""

import scipy.linalg as linalg
import scipy.optimize as opt
import numpy as np
import qutip as qt
import lmfit as lm


class Hcpb(object):
    """
    Hcpb class. Used to model analytically the CPB Hamiltonian quickly
    and efficiently. Solves tridiagonal eigenvalue problem for arbitrary
    Ej, Ec, ng values.

    As long as nlevels remains fixed the number of charge states
    considered does not change and it does not recreate the arrays,
    just recomputes the properties

    Returns all properties of interest for the CPB.

    """
    def __init__(self, nlevels=15, Ej=None, Ec=None, ng=0.5):
        """
        Generate a CPB model

        kwargs:
            nlevels (int): number of charge states of the CPB [-nlevels, nlevels+1]
            Ej (float): Josephson energy of the JJ
            Ec (float): Charging energy of the CPB
            ng (float): offset charge of the CPB
        """

        self._nlevels = nlevels
        self._Ej = Ej
        self._Ec = Ec
        self._ng = ng
        self.evals = None
        self.evecs = None
        # Generate the diagonal and offdiagonal components of the Hamiltonian
        self._gen_operators()
        # compute the eigenvectors and eigenvalues of the CPB
        # all properties can be derived from these
        self._calc_H()

    def _gen_operators(self):
        '''
        Generate at initialization the number of levels and only recompute
        the size of the problem if nlevels changes
        '''

        self._diag = np.arange(-self._nlevels, self._nlevels + 1)
        self._off = np.ones(len(self._diag) - 1)

    def _calc_H(self):
        '''
        Only diagonalize the Hamiltonian if the CPB is supplied with the
        three mandatory parameters Ej, Ec, ng, but allow for them to not
        be set at initialization.
        '''
        if (self._Ej is None) or (self._Ec is None) or (self._ng is None):
            self.evals = None
            self.evecs = None
        else:
            self._diagonalize_H()

    def _diagonalize_H(self):
        '''
        Diagonalize the CPB Hamiltonian using symmetric tridiagonal
        eigensolver for efficient calculation of properties
        '''
        ham_diag = 4 * self._Ec * (self._diag - self._ng)**2
        ham_off = -(self._Ej / 2.0) * self._off
        evals, evecs = linalg.eigh_tridiagonal(ham_diag, ham_off)
        self.evals = np.real(np.array(evals))
        self.evecs = np.array(evecs)

    def evalue_k(self, k):
        '''
        Return the eigenvalue of the Hamiltonian for level k

        Arguments:
            k (int): index of the eigenvalue

        Returns:
            (float): eigenvalue of the Hamiltonian
        '''
        return self.evals[k]

    def evec_k(self, k):
        '''
        Return the eigenvector of the CPB Hamiltonian for
        level k.

        Arguments:
            k (int): index of eigenvector

        Returns:
            (array): eigenvector of the |k> level of the
                     CPB Hamiltonian
        '''
        return self.evecs[:, k]

    def psi_k(self, k, pts=1001):
        '''
        Return the wavevector of the CPB Hamiltonian
        in the flux basis. Made compact over the interval
        of [-pi, pi]

        Arguments:
            k (int): index of wavevector corresponding to the
                     |k> eigenstate

        Keyword Arguments:
            pts (int): # of points to approximate the wavevector
                       in the interval [-pi, pi]

        Returns:
            (array): Wavevector corresponding the |k> eigenstate
        '''
        phi = np.linspace(-np.pi, np.pi, pts)
        evec = self.evecs[:, k]
        n = np.arange(-self._nlevels, self._nlevels + 1)
        psi = []
        for i, val in enumerate(n):
            # Get Fourier component of each charge basis state
            psi.append(evec[i] * np.exp(1j * val * phi))
        psi = np.array(psi)
        # Sum over Fourier components to get eigenwave
        psi = np.sum(psi, axis=0) / np.sqrt(2 * np.pi)
        return psi

    def fij(self, i, j):
        '''
        Compute the transition energy between states
        |i> and |j>

        Arguments:
            i (int): index of state |i>
            j (int): index of state |j>

        Returns:
            (float): Eij, the transition energy
        '''
        return np.abs(self.evalue_k(i) - self.evalue_k(j))

    def anharm(self):
        '''
        Compute the anharmonicity of the CPB

        Returns:
            (float): Anharmonicty defined as E12-E01
        '''
        return self.fij(1, 2) - self.fij(0, 1)

    def n_ij(self, i, j):
        '''
        Compute the value of the number operator for
        coupling elements together

        Arguments:
            i (int): |i> index of the transmon
            j (int): |j> index of the transmon

        Returns:
            (float): matrix element corresponding to the
                     number operator in the transmon basis
                     n_ij = |<i|n|j>|
        '''
        n_op = np.arange(-self._nlevels, self._nlevels + 1)
        n_ij = np.conj(self.evec_k(i)) * n_op * self.evec_k(j)
        n_ij = np.abs(np.sum(n_ij))
        return n_ij

    def phi_ij(self, i, j, parity):
        if int(parity % 2):
            cos_phi = np.diag(len(self._diag) - 1, k=1) + np.diag(len(self._diag) - 1, k=-1)
            cos_ij = np.conj(self.evec_k(i)) * cos_phi * self.evec_k(j)
            cos_ij = np.abs(np.sum(cos_ij))
            return cos_ij
        else:
            sin_phi = np.diag(len(self._diag) - 1, k=1) - np.diag(len(self._diag) - 1, k=-1)
            sin_ij = np.conj(self.evec_k(i)) * sin_phi * self.evec_k(j)
            sin_ij = np.abs(np.sum(sin_ij))
            return sin_ij



    def h0_to_qutip(self, n_transmon):
        '''
        Wrapper around Qutip to output the diagonalized
        Hamiltonian truncated up to n levels of the transmon
        for modeling

        Arguments:
            n_transmon (int): Truncate up to n levels of the
                              Transmon Hamiltonian
        Returns:
            (Qobj): Returns a Qutip Qobj for the diagonalized
                    transmon
        '''
        ham = np.diag(self.evals[:n_transmon] - self.evals[0])
        return qt.Qobj(ham)

    def n_to_qutip(self, n_transmon, thresh=None):
        '''
        Wrapper around Qutip to output the number operator
        for the Transmon Hamiltonian for computing the
        coupling between other elements in the system.

        Arguments:
            n_transmon (int): number of levels to consider

        Keyword Arguments:
            thresh (float): threshold for keeping small values
                            in the number operator i.e n_{i,i+2}
                            terms drop off exponentially. If None
                            retain all terms.

        Returns:
            (Qobj): Returns a Qutip Qobj corresponding to the
                    number operator for defining couplings
        '''
        n_op = np.zeros((n_transmon, n_transmon))
        for i in range(n_transmon):
            for j in range(n_transmon):
                if i == j:
                    n_op[i, j] = 0
                else:
                    val = self.n_ij(i, j)
                    if thresh is not None:
                        if val < thresh:
                            val = 0
                    n_op[i, j] = val
        return qt.Qobj(n_op)

    def params_from_spectrum(self, f01, anharm, verbose=False, **kwargs):
        '''
        Method to work backwards from a desired transmon
        frequency and anharmonicty to extract the target
        Ej and Ec for design and fabrication. Updates the
        class to include these Ej and Ec as the new values
        for extracting properties.

        Wraps around the lmfit minimize class and can inherit
        any kwargs from that class

        Arguments:
            f01 (float): Desired qubit frequency
            anharm (float): Desired qubit anharmonicity

        KeyWords:
            verbose (boolean): return the result of the
                lmfit class or just return Ej, Ec.
                Default: return just Ej, Ec

        

        Returns:
            (float, float): Ej and Ec of the transmon Hamiltonian
                            corresponding to the f01 and anharmonicty
                            of the device
        '''
        # Anharmonicty should be negative for the Transmon
        if anharm > 0:
            anharm = -anharm

        def fun(params, f01, anharm):
            self.Ej = params['Ej'].value
            self.Ec = params['Ec'].value
            res_f01 = self.fij(0,1) - f01
            res_anharm = 10*(self.anharm() - anharm)

            return np.array([res_f01, res_anharm])


        params = lm.Parameters()
        p0 = [(f01 - anharm)**2 / (8 * (-anharm)), -anharm]
        params.add('Ej', 
                   value=p0[0],
                   min=0,
                   max=1.5*p0[0])
        params.add('Ec', 
                   value=p0[1],
                   min=0,
                   max=1.5*p0[1])
        ops = dict(args=([f01, anharm]))
        res = lm.minimize(fun, params, **{**ops, **kwargs})
        if verbose:
            return res
        else:
            return res.params['Ej'].value, res.params['Ec'].value

    @property
    def nlevels(self):
        '''Return the number of levels'''
        return self._nlevels

    @nlevels.setter
    def nlevels(self, value):
        '''
        Set the number of levels and recompute the Hamiltonian
        with the new size
        '''
        self._nlevels = value
        self.__init__(value, self._Ej, self._Ec, self._ng)

    @property
    def Ej(self):
        '''Returns Ej'''
        return self._Ej

    @Ej.setter
    def Ej(self, value):
        '''Set Ej and recompute properties'''
        self._Ej = value
        self._calc_H()

    @property
    def Ec(self):
        '''Return Ec'''
        return self._Ec

    @Ec.setter
    def Ec(self, value):
        '''Set Ec and recompute properties'''
        self._Ec = value
        self._calc_H()

    @property
    def ng(self):
        '''Return ng '''
        return self._ng

    @ng.setter
    def ng(self, value):
        '''Set ng and recompute properties'''
        self._ng = value
        self._calc_H()


if __name__ == '__main__':
    pass