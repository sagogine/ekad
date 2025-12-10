/**
 * @name Subprocess Calls
 * @description Extract subprocess.run, os.system, and Popen calls
 * @kind graph
 * @problem.severity info
 * @id python/subprocess-calls
 */

import python

// Subprocess.run calls
from Call call, Function func, string script_path
where
  call.getTarget().(Function).hasQualifiedName("subprocess", "run") and
  func = call.getEnclosingFunction() and
  script_path = call.getArgument(0).(StringLiteral).getValue()
select func, "RUNS_SUBPROCESS", script_path

// os.system calls
from Call call, Function func, string command
where
  call.getTarget().(Function).hasQualifiedName("os", "system") and
  func = call.getEnclosingFunction() and
  command = call.getArgument(0).(StringLiteral).getValue()
select func, "RUNS_SUBPROCESS", command

// Popen calls
from Call call, Function func, string command
where
  call.getTarget().(Function).hasQualifiedName("subprocess", "Popen") and
  func = call.getEnclosingFunction() and
  command = call.getArgument(0).(StringLiteral).getValue()
select func, "RUNS_SUBPROCESS", command

