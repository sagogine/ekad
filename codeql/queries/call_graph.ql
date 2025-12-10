/**
 * @name Function Call Graph
 * @description Extract function call relationships (caller -> callee)
 * @kind graph
 * @problem.severity info
 * @id python/function-calls
 */

import python

from FunctionCall call, Function caller, Function callee
where
  call.getTarget() = callee and
  caller = call.getEnclosingFunction()
select caller, "CALLS", callee

