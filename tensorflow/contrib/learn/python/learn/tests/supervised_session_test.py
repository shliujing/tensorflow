# pylint: disable=g-bad-file-header
# Copyright 2016 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Tests for SupervisedSession."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

import tensorflow as tf

from tensorflow.contrib.learn.python.learn import supervised_session


class ScaffoldTest(tf.test.TestCase):
  """Scaffold tests."""

  def test_defaults_empty_graph(self):
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      self.assertTrue(isinstance(scaffold.global_step_tensor, tf.Variable))
      self.assertTrue(isinstance(scaffold.init_op, tf.Operation))
      self.assertEqual(None, scaffold.init_feed_dict)
      self.assertEqual(None, scaffold.init_fn)
      self.assertTrue(isinstance(scaffold.ready_op, tf.Tensor))
      self.assertTrue(isinstance(scaffold.local_init_op, tf.Operation))
      self.assertTrue(isinstance(scaffold.saver, tf.train.Saver))
      with self.test_session() as sess:
        self.assertTrue(b'global_step' in sess.run(scaffold.ready_op))
        sess.run([scaffold.init_op, scaffold.local_init_op])
        self.assertEquals(0, len(sess.run(scaffold.ready_op)))
        self.assertEquals(0, sess.run(scaffold.global_step_tensor))

  def test_caches_values(self):
    with tf.Graph().as_default():
      scaffold1 = supervised_session.Scaffold()
      scaffold2 = supervised_session.Scaffold()
      self.assertEqual(scaffold1.global_step_tensor,
                       scaffold2.global_step_tensor)
      self.assertEqual(scaffold1.init_op, scaffold2.init_op)
      self.assertEqual(scaffold1.ready_op, scaffold2.ready_op)
      self.assertEqual(scaffold1.local_init_op, scaffold2.local_init_op)
      self.assertEqual(scaffold1.saver, scaffold2.saver)

  def test_uses_passed_values(self):
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold(global_step_tensor=1,
                                             init_op=2,
                                             init_feed_dict=3,
                                             init_fn=lambda scaffold, sess: 4,
                                             ready_op=5,
                                             local_init_op=6,
                                             saver=7)
      self.assertEqual(1, scaffold.global_step_tensor)
      self.assertEqual(2, scaffold.init_op)
      self.assertEqual(3, scaffold.init_feed_dict)
      self.assertTrue(callable(scaffold.init_fn))
      self.assertEqual(5, scaffold.ready_op)
      self.assertEqual(6, scaffold.local_init_op)
      self.assertEqual(7, scaffold.saver)


class RaiseOnceAtStepN(tf.contrib.learn.monitors.BaseMonitor):
  """Monitor that raises an Exception at step N."""

  def __init__(self, n, ex):
    super(RaiseOnceAtStepN, self).__init__()
    self.n = n
    self.ex = ex
    self.raised = False

  def step_begin(self, step):
    super(RaiseOnceAtStepN, self).step_begin(step)
    # Raise the first time we reach step N.
    if step == self.n and not self.raised:
      self.raised = True
      raise self.ex
    return []


class SupervisedSessionTest(tf.test.TestCase):
  """SupervisedSession tests."""

  def _test_dir(self, test_name):
    """Create an empty dir to use for tests.

    Args:
      test_name: Name of the test.

    Returns:
      Absolute path to the test directory.
    """
    test_dir = os.path.join(self.get_temp_dir(), test_name)
    if os.path.isdir(test_dir):
      os.removedirs(test_dir)
    os.makedirs(test_dir)
    return test_dir

  def test_defaults(self):
    with tf.Graph().as_default():
      with supervised_session.SupervisedSession('') as session:
        self.assertEqual(0, session.run(session.scaffold.global_step_tensor))

  def test_last_step(self):
    logdir = self._test_dir('test_last_step')
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      gstep = scaffold.global_step_tensor
      do_step = tf.assign_add(gstep, 1)
      # Run till step 3 and save.
      monitors = [tf.contrib.learn.monitors.StopAtStep(last_step=3)]
      with supervised_session.SupervisedSession('', scaffold=scaffold,
                                                monitors=monitors) as session:
        self.assertEqual(0, session.run(gstep))
        self.assertFalse(session.should_stop())
        self.assertEqual(1, session.run(do_step))
        self.assertFalse(session.should_stop())
        self.assertEqual(2, session.run(do_step))
        self.assertFalse(session.should_stop())
        self.assertEqual(3, session.run(do_step))
        self.assertTrue(session.should_stop())
        save_path = scaffold.saver.save(session.session,
                                        os.path.join(logdir, 'step-3'))
      # Run till step 5 and save.
      def load_ckpt(scaffold, sess):
        scaffold.saver.restore(sess, save_path)
      scaffold = supervised_session.Scaffold(init_fn=load_ckpt)
      monitors = [tf.contrib.learn.monitors.StopAtStep(last_step=5)]
      with supervised_session.SupervisedSession('', scaffold=scaffold,
                                                monitors=monitors) as session:
        self.assertEqual(3, session.run(gstep))
        self.assertFalse(session.should_stop())
        self.assertEqual(4, session.run(do_step))
        self.assertFalse(session.should_stop())
        self.assertEqual(5, session.run(do_step))
        self.assertTrue(session.should_stop())

  def test_num_steps(self):
    logdir = self._test_dir('test_num_steps')
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      gstep = scaffold.global_step_tensor
      do_step = tf.assign_add(gstep, 1)
      # Do 3 steps and save.
      monitors = [tf.contrib.learn.monitors.StopAtStep(num_steps=3)]
      with supervised_session.SupervisedSession('', scaffold=scaffold,
                                                monitors=monitors) as session:
        session.run(do_step)
        self.assertFalse(session.should_stop())
        session.run(do_step)
        self.assertFalse(session.should_stop())
        session.run(do_step)
        self.assertTrue(session.should_stop())
        save_path = scaffold.saver.save(session.session,
                                        os.path.join(logdir, 'step-3'))
      # Restore and do 4 steps.
      def load_ckpt(scaffold, sess):
        scaffold.saver.restore(sess, save_path)
      scaffold = supervised_session.Scaffold(init_fn=load_ckpt)
      monitors = [tf.contrib.learn.monitors.StopAtStep(num_steps=4)]
      with supervised_session.SupervisedSession('', scaffold=scaffold,
                                                monitors=monitors) as session:
        self.assertEqual(3, session.run(gstep))
        session.run(do_step)
        self.assertFalse(session.should_stop())
        session.run(do_step)
        self.assertFalse(session.should_stop())
        session.run(do_step)
        self.assertFalse(session.should_stop())
        session.run(do_step)
        self.assertTrue(session.should_stop())

  # This set of tests, verifies the supervised session behavior when exceptions
  # are raised next to the innermost session run() call.

  def test_recovery(self):
    logdir = self._test_dir('test_recovery')
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      gstep = scaffold.global_step_tensor
      do_step = tf.assign_add(gstep, 1)
      # Use a monitor to save the model every 100 steps.  It also saves it at
      # the end.
      monitors = [tf.contrib.learn.monitors.CheckpointSaver(
          100, scaffold.saver, logdir)]
      with supervised_session.SupervisedSession('', scaffold=scaffold,
                                                checkpoint_dir=logdir,
                                                monitors=monitors) as session:
        self.assertEqual(0, session.run(gstep))
        self.assertEqual(1, session.run(do_step))
        self.assertEqual(2, session.run(do_step))
      # A restart will find the checkpoint and recover automatically.
      with supervised_session.SupervisedSession(
          '', scaffold=scaffold, checkpoint_dir=logdir) as session:
        self.assertEqual(2, session.run(gstep))

  def test_retry_on_aborted_error(self):
    # Tests that we silently retry on abort.  Note that this does not test
    # recovery as we do not use a CheckpointSaver in this test.
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      gstep = scaffold.global_step_tensor
      do_step = tf.assign_add(gstep, 1)
      monitor = RaiseOnceAtStepN(3, tf.errors.AbortedError(None, None, 'Abort'))
      with supervised_session.SupervisedSession('', scaffold=scaffold,
                                                monitors=[monitor]) as session:
        self.assertEqual(0, session.run(gstep))
        self.assertEqual(1, session.run(do_step))
        self.assertEqual(2, session.run(do_step))
        self.assertFalse(session.should_stop())
        # Here at step 3, the monitor triggers and raises AbortedError.  The
        # SupervisedSession automatically retries and restart from a freshly
        # initialized session, so the step is back to 0 and running do_step
        # moves it to 1.
        self.assertEqual(1, session.run(do_step))
        self.assertFalse(session.should_stop())
        self.assertTrue(monitor.raised)
        self.assertEqual(2, session.run(do_step))
        self.assertFalse(session.should_stop())

  def test_recover_and_retry_on_aborted_error(self):
    # Tests that we silently retry and recover on abort.  This test uses
    # a CheckpointSaver to have something to recover from.
    logdir = self._test_dir('test_recover_and_retry_on_aborted_error')
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      gstep = scaffold.global_step_tensor
      do_step = tf.assign_add(gstep, 1)
      abort_monitor = RaiseOnceAtStepN(
          3, tf.errors.AbortedError(None, None, 'Abort'))
      # Save after each step.
      ckpt_monitor = tf.contrib.learn.monitors.CheckpointSaver(
          1, scaffold.saver, logdir)
      monitors = [abort_monitor, ckpt_monitor]
      with supervised_session.SupervisedSession('', scaffold=scaffold,
                                                checkpoint_dir=logdir,
                                                monitors=monitors) as session:
        self.assertEqual(0, session.run(gstep))
        self.assertEqual(1, session.run(do_step))
        self.assertEqual(2, session.run(do_step))
        self.assertFalse(session.should_stop())
        # Here at step 3, the monitor triggers and raises AbortedError.  The
        # SupervisedSession automatically restores and retries.
        self.assertEqual(3, session.run(do_step))
        self.assertTrue(abort_monitor.raised)
        self.assertFalse(session.should_stop())
        self.assertEqual(4, session.run(do_step))
        self.assertFalse(session.should_stop())

  def test_stop_cleanly_on_out_of_range_exception(self):
    # Tests that we stop cleanly when OutOfRange is raised.
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      gstep = scaffold.global_step_tensor
      do_step = tf.assign_add(gstep, 1)
      monitor = RaiseOnceAtStepN(
          3, tf.errors.OutOfRangeError(None, None, 'EOI'))
      with supervised_session.SupervisedSession('', scaffold=scaffold,
                                                monitors=[monitor]) as session:
        self.assertEqual(0, session.run(gstep))
        self.assertEqual(1, session.run(do_step))
        self.assertEqual(2, session.run(do_step))
        self.assertFalse(session.should_stop())
        # Here at step 3, the monitor triggers and raises OutOfRange.  The
        # session should go into should_stop() mode.  We do not get a result
        # in that case.
        self.assertEqual(None, session.run(do_step))
        self.assertTrue(monitor.raised)
        self.assertTrue(session.should_stop())

  def test_stop_cleanly_on_custom_exception(self):
    # Tests that we stop cleanly when an exception type of
    # our choice is raised (StopIteration here.)
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      gstep = scaffold.global_step_tensor
      do_step = tf.assign_add(gstep, 1)
      monitor = RaiseOnceAtStepN(3, StopIteration('I choose you'))
      exception_types = [tf.errors.OutOfRangeError, StopIteration]
      with supervised_session.SupervisedSession(
          '', scaffold=scaffold,
          monitors=[monitor],
          clean_stop_exception_types=exception_types) as session:
        self.assertEqual(0, session.run(gstep))
        self.assertEqual(1, session.run(do_step))
        self.assertEqual(2, session.run(do_step))
        self.assertFalse(session.should_stop())
        # Here at step 3, the monitor triggers and raises StopIteration.  The
        # session should go into should_stop() mode.  We do not get a result
        # in that case.
        self.assertEqual(None, session.run(do_step))
        self.assertTrue(monitor.raised)
        self.assertTrue(session.should_stop())

  # This set of tests, verifies the session behavior when exceptions are raised
  # from code inside a "with SupervisedSession:" context.

  def test_regular_exception_pass_through_in_with_body(self):
    # Tests that regular exceptions just pass through a "with
    # SupervisedSession" block and set the session in stop mode.
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      gstep = scaffold.global_step_tensor
      do_step = tf.assign_add(gstep, 1)
      monitor = RaiseOnceAtStepN(3, RuntimeError('regular exception'))
      session = supervised_session.SupervisedSession('', scaffold=scaffold,
                                                     monitors=[monitor])
      with self.assertRaisesRegexp(RuntimeError, 'regular exception'):
        with session:
          self.assertEqual(0, session.run(gstep))
          self.assertEqual(1, session.run(do_step))
          self.assertEqual(2, session.run(do_step))
          self.assertFalse(session.should_stop())
          # This triggers the monitor and raises the exception
          session.run(do_step)
          # We should not hit this
          self.assertFalse(True)
      self.assertTrue(monitor.raised)
      self.assertTrue(session.should_stop())

  def test_stop_cleanly_when_no_exception_in_with_body(self):
    # Tests that regular exceptions pass through
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      gstep = scaffold.global_step_tensor
      do_step = tf.assign_add(gstep, 1)
      session = supervised_session.SupervisedSession('', scaffold=scaffold)
      with session:
        self.assertEqual(1, session.run(do_step))
        self.assertEqual(2, session.run(do_step))
        self.assertFalse(session.should_stop())
      # Should have closed.
      self.assertTrue(session.should_stop())
      self.assertTrue(session._is_closed())

  def test_stop_cleanly_on_out_of_range_exception_in_with_body(self):
    # Tests that regular exceptions pass through
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      gstep = scaffold.global_step_tensor
      do_step = tf.assign_add(gstep, 1)
      session = supervised_session.SupervisedSession('', scaffold=scaffold)
      with session:
        self.assertEqual(1, session.run(do_step))
        self.assertEqual(2, session.run(do_step))
        self.assertFalse(session.should_stop())
        raise tf.errors.OutOfRangeError(None, None, 'EOI')
      # Should have closed.
      self.assertTrue(session.should_stop())
      self.assertTrue(session._is_closed())

  def test_raises_regular_exceptions_in_with_body(self):
    # Tests that regular exceptions in "with body" are seen outside.
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      gstep = scaffold.global_step_tensor
      do_step = tf.assign_add(gstep, 1)
      session = supervised_session.SupervisedSession('', scaffold=scaffold)
      # We should see that exception.
      with self.assertRaisesRegexp(RuntimeError, 'regular exception'):
        with session:
          self.assertEqual(1, session.run(do_step))
          self.assertEqual(2, session.run(do_step))
          self.assertFalse(session.should_stop())
          # Will be visible outside the "with body".
          raise RuntimeError('regular exception')
      # Should have closed.
      self.assertTrue(session.should_stop())
      self.assertTrue(session._is_closed())

  def test_stop_cleanly_on_custom_exception_in_with_body(self):
    with tf.Graph().as_default():
      scaffold = supervised_session.Scaffold()
      gstep = scaffold.global_step_tensor
      do_step = tf.assign_add(gstep, 1)
      exception_types = [tf.errors.OutOfRangeError, StopIteration]
      session = supervised_session.SupervisedSession(
          '', scaffold=scaffold, clean_stop_exception_types=exception_types)
      with session:
        self.assertEqual(1, session.run(do_step))
        self.assertEqual(2, session.run(do_step))
        self.assertFalse(session.should_stop())
        raise StopIteration('EOI')
      # Should have closed.
      self.assertTrue(session.should_stop())
      self.assertTrue(session._is_closed())


if __name__ == '__main__':
  tf.test.main()
