/**
 * @name Import Relationships
 * @description Extract import statements (file -> imported module)
 * @kind graph
 * @problem.severity info
 * @id python/imports
 */

import python

// Import statements
from Import import_stmt, File file, string module_name
where
  file = import_stmt.getFile() and
  module_name = import_stmt.getImportedName()
select file, "IMPORTS", module_name

// From imports
from ImportFrom from_import, File file, string module_name
where
  file = from_import.getFile() and
  module_name = from_import.getImportedName()
select file, "IMPORTS", module_name

