"""
All code fragments that are embedded in the API conversion document for the auto_ivc feature
are tested here.
"""
import unittest

import openmdao.api as om
from openmdao.core.tests.test_distribcomp import DistribInputDistribOutputComp
from openmdao.test_suite.components.unit_conv import TgtCompC, TgtCompF, TgtCompK
from openmdao.utils.mpi import MPI
from openmdao.utils.assert_utils import assert_near_equal

try:
    from openmdao.vectors.petsc_vector import PETScVector
except ImportError:
    PETScVector = None


class TestConversionGuideDoc(unittest.TestCase):

    def test_tldr(self):
        import openmdao.api as om

        # build the model
        prob = om.Problem()

        prob.model.add_subsystem('paraboloid',
                                 om.ExecComp('f = (x-3)**2 + x*y + (y+4)**2 - 3'),
                                 promotes_inputs=['x', 'y'])

        # setup the optimization
        prob.driver = om.ScipyOptimizeDriver()
        prob.driver.options['optimizer'] = 'SLSQP'

        prob.model.add_design_var('x', lower=-50, upper=50)
        prob.model.add_design_var('y', lower=-50, upper=50)
        prob.model.add_objective('paraboloid.f')

        prob.setup()
        
        prob['x'] = 3.0
        prob['y'] = -4.0
        
        prob.run_driver()

        # minimum value
        assert_near_equal(prob['paraboloid.f'], -27.33333, 1e-6)

        # location of the minimum
        assert_near_equal(prob['x'], 6.6667, 1e-4)
        assert_near_equal(prob['y'], -7.33333, 1e-4)

    def test_get_set(self):
        import openmdao.api as om

        # build the model
        prob = om.Problem()

        prob.model.add_subsystem('paraboloid',
                                 om.ExecComp('f = (x-3)**2 + x*y + (y+4)**2 - 3'),
                                 promotes_inputs=['x', 'y'])

        prob.setup()
        
        x = prob.get_val('x')
        prob.set_val('y', 15.0)
        
    def test_constrained(self):
        import openmdao.api as om

        # We'll use the component that was defined in the last tutorial
        from openmdao.test_suite.components.paraboloid import Paraboloid

        # build the model
        prob = om.Problem()
        prob.model.add_subsystem('parab', Paraboloid(), 
                                 promotes_inputs=['x', 'y'])

        # define the component whose output will be constrained
        prob.model.add_subsystem('const', om.ExecComp('g = x + y'), 
                                 promotes_inputs=['x', 'y'])

        # Design variables 'x' and 'y' span components, so we need to provide a common initial
        # value for them.
        prob.model.set_input_defaults('x', 3.0)
        prob.model.set_input_defaults('y', -4.0)

        # setup the optimization
        prob.driver = om.ScipyOptimizeDriver()
        prob.driver.options['optimizer'] = 'COBYLA'

        prob.model.add_design_var('x', lower=-50, upper=50)
        prob.model.add_design_var('y', lower=-50, upper=50)
        prob.model.add_objective('parab.f_xy')

        # to add the constraint to the model
        prob.model.add_constraint('const.g', lower=0, upper=10.)

        prob.setup()
        prob.run_driver()

        # minimum value
        assert_near_equal(prob.get_val('parab.f_xy'), -27., 1e-6)

        # location of the minimum
        assert_near_equal(prob.get_val('x'), 7, 1e-4)
        assert_near_equal(prob.get_val('y'), -7, 1e-4)
    
    def test_promote_new_name(self):
         
        prob = om.Problem()
        
        prob.model.add_subsystem('paraboloid',
                                 om.ExecComp('f = (x-3)**2 + x*y + (y+4)**2 - 3'),
                                 promotes_inputs=[('x', 'width'), ('y', 'length')])

        # Could also set these after setup.
        prob.model.set_input_defaults('width', 3.0)
        prob.model.set_input_defaults('length', -4.0)
        
        prob.setup()
        prob.run_model()
        
        assert_near_equal(prob.get_val('width'), 3.0)

    def test_units(self):
        
        prob = om.Problem()
        
        # Input units in degF
        prob.model.add_subsystem('tgtF', TgtCompF(), 
                                 promotes_inputs=['x2'])

        # Input units in degC
        prob.model.add_subsystem('tgtC', TgtCompC(), 
                                 promotes_inputs=['x2'])

        # Input units in degK
        prob.model.add_subsystem('tgtK', TgtCompK(), 
                                 promotes_inputs=['x2'])        
        
        prob.model.set_input_defaults('x2', 100.0, units='degC')
        
        prob.setup()
        prob.run_model()
        
        assert_near_equal(prob.get_val('x2', 'degF'), 212.0)
        
    def test_promote_src_indices(self):
        import numpy as np

        import openmdao.api as om

        class MyComp1(om.ExplicitComponent):
            def setup(self):
                # this input will connect to entries 0, 1, and 2 of its source
                self.add_input('x', np.ones(3), src_indices=[0, 1, 2])
                self.add_output('y', 1.0)

            def compute(self, inputs, outputs):
                outputs['y'] = np.sum(inputs['x'])*2.0

        class MyComp2(om.ExplicitComponent):
            def setup(self):
                # this input will connect to entries 3 and 4 of its source
                self.add_input('x', np.ones(2), src_indices=[3, 4])
                self.add_output('y', 1.0)

            def compute(self, inputs, outputs):
                outputs['y'] = np.sum(inputs['x'])*4.0

        p = om.Problem()

        # IndepVarComp is required to define the full size of the source vector.
        p.model.add_subsystem('indep', om.IndepVarComp('x', np.ones(5)),
                              promotes_outputs=['x'])
        p.model.add_subsystem('C1', MyComp1(), promotes_inputs=['x'])
        p.model.add_subsystem('C2', MyComp2(), promotes_inputs=['x'])

        p.model.add_design_var('x')
        p.setup()
        p.run_model()

        assert_near_equal(p.get_val('C1.x'), np.ones(3))
        assert_near_equal(p.get_val('C1.y'), 6.)
        assert_near_equal(p.get_val('C2.x'), np.ones(2))
        assert_near_equal(p.get_val('C2.y'), 8.)
        

@unittest.skipUnless(MPI and PETScVector, "MPI and PETSc are required.")
class TestConversionGuideDocMPI(unittest.TestCase):

    N_PROCS = 4

    def test_prob_getval_dist_par(self):
        import numpy as np

        import openmdao.api as om

        size = 3

        p = om.Problem()
        top = p.model
        par = top.add_subsystem('par', om.ParallelGroup())

        # An IndepVarComp is required on all unconnected distributed inputs.
        ivc = om.IndepVarComp()
        ivc.add_output('invec1', np.ones(size))
        ivc.add_output('invec2', np.ones(size))
        top.add_subsystem('P', ivc)
        top.connect('P.invec1', 'par.C1.invec')
        top.connect('P.invec2', 'par.C2.invec')

        C1 = par.add_subsystem("C1", DistribInputDistribOutputComp(arr_size=size))
        C2 = par.add_subsystem("C2", DistribInputDistribOutputComp(arr_size=size))

        p.setup()

        p['P.invec1'] = np.array([2, 1, 1], float)
        p['P.invec2'] = np.array([6, 3, 3], float)

        p.run_model()

        ans = p.get_val('par.C2.invec', get_remote=True)
        np.testing.assert_allclose(ans, np.array([6, 3,3], dtype=float))
        ans = p.get_val('par.C2.outvec', get_remote=True)
        np.testing.assert_allclose(ans, np.array([12, 6, 6], dtype=float))
        ans = p.get_val('par.C1.invec', get_remote=True)
        np.testing.assert_allclose(ans, np.array([2, 1, 1], dtype=float))
        ans = p.get_val('par.C1.outvec', get_remote=True)
        np.testing.assert_allclose(ans, np.array([4, 2, 2], dtype=float))


if __name__ == "__main__":

    unittest.main()
