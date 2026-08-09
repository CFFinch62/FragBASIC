"""
Control flow structures for the BASIC interpreter.
Handles IF, FOR, WHILE, DO, SELECT CASE, and related constructs.
"""

from .ast_nodes import Node, NodeType
from .variable import Variable
from .interpreter_core import ExitException


class InterpreterControl:
    """
    Mixin class for control flow structures in the BASIC interpreter.
    """

    def visit_block(self, node):
        """Visit a BLOCK node (sequence of statements)"""
        result = None
        statements = node.nodes
        i = 0

        # Store reference to root statements for GOSUB
        if not hasattr(self, 'root_statements'):
            self.root_statements = statements

        while i < len(statements):
            # Cooperative cancellation checkpoint (Ctrl+C, --timeout, IDE Stop)
            self.check_cancelled()

            statement = statements[i]

            # Set current statement index for loop handling
            self.current_statement_index = i

            # Handle GOSUB jumps
            if statement.type == NodeType.GOSUB:
                # Store return address on gosub stack
                self.gosub_stack.append(i + 1)  # Return to next statement

                # Find target line number
                if statement.value is not None:
                    target_line = statement.value
                    # Find the statement with this line number
                    for j, stmt in enumerate(statements):
                        if stmt.type == NodeType.LINE_NUMBER and stmt.value == target_line:
                            # Jump to this line
                            i = j
                            break
                    else:
                        self.error(f"Line number {target_line} not found")
                    continue
                elif statement.name is not None:
                    target_label = statement.name
                    # Use pre-collected labels
                    if target_label in self.labels:
                        # Find the statement with this label in the current block
                        for j, stmt in enumerate(statements):
                            if stmt.type == NodeType.LABEL and stmt.name == target_label:
                                # Jump to this line
                                i = j
                                break
                        else:
                            self.error(f"Label {target_label} not found in current block")
                    else:
                        self.error(f"Label {target_label} not found")
                    continue

            # Handle RETURN jumps
            elif statement.type == NodeType.RETURN:
                result = self.visit(statement)
                if self.gosub_stack:
                    # Jump back to return address
                    return_addr = self.gosub_stack.pop()
                    i = return_addr
                    continue
                else:
                    # RETURN without GOSUB. Visited exactly once (above) -
                    # `continue` here so this statement never falls through
                    # into the FOR/WHILE/else dispatch further down and gets
                    # visited (and any side-effecting expression inside it,
                    # like a recursive call, re-evaluated) a second time.
                    # If it was a real FUNCTION/SUB/expression return, stop
                    # this block now; a truly bare RETURN with nothing
                    # pending is the documented no-op - just move on.
                    if self.return_value is not None or (
                        getattr(self, '_proc_call_depth', 0) > 0 and (
                            getattr(self, 'function_returned', False) or getattr(self, 'sub_returned', False)
                        )
                    ):
                        break
                    i += 1
                    continue

            # Handle END statement
            elif statement.type == NodeType.END:
                result = self.visit(statement)
                # END terminates the program
                break

            # Handle FOR statement - execute the entire loop
            if statement.type == NodeType.FOR:
                result = self.execute_for_loop(statement, statements, i)
                # Skip to the statement after the matching NEXT
                i = self.find_matching_next(statements, i)
            # Handle WHILE statement - store the index for jumping back
            elif statement.type == NodeType.WHILE:
                result = self.visit(statement)
                # WHILE is pre-test: check the condition now, before ever
                # entering the body (this used to only be checked at WEND,
                # so the body always ran at least once even when the
                # condition started false - a WHILE behaved like DO...LOOP
                # WHILE instead of the documented top-checked loop).
                if hasattr(self, 'while_stack') and self.while_stack:
                    loop_info = self.while_stack[-1]
                    condition = self.visit(loop_info['condition_node'])
                    if condition.to_single() == 0:
                        self.while_stack.pop()
                        i = self.find_matching_wend(statements, i)
                    else:
                        loop_info['while_index'] = i + 1
            # Skip NEXT statements (they're handled by FOR loops)
            elif statement.type == NodeType.NEXT:
                # NEXT statements are processed by execute_for_loop, so skip them
                pass
            else:
                try:
                    result = self.visit(statement)
                except ExitException as exit_ex:
                    # Handle EXIT statements
                    if exit_ex.exit_type == 'WHILE' and hasattr(self, 'while_stack') and self.while_stack:
                        # Exit the current WHILE loop
                        self.while_stack.pop()
                        # Skip to after the matching WEND
                        wend_found = False
                        nest_level = 0
                        for j in range(i + 1, len(statements)):
                            stmt = statements[j]
                            if stmt.type == NodeType.WHILE:
                                nest_level += 1
                            elif stmt.type == NodeType.WEND:
                                if nest_level == 0:
                                    i = j
                                    wend_found = True
                                    break
                                else:
                                    nest_level -= 1
                        if not wend_found:
                            self.error("EXIT WHILE without matching WEND")
                    elif exit_ex.exit_type == 'DO' and hasattr(self, 'do_stack') and self.do_stack:
                        # Exit the current DO loop
                        self.do_stack.pop()
                        # Skip to after the matching LOOP
                        loop_found = False
                        nest_level = 0
                        for j in range(i + 1, len(statements)):
                            stmt = statements[j]
                            if stmt.type == NodeType.DO_LOOP:
                                nest_level += 1
                            elif stmt.type == NodeType.LOOP:
                                if nest_level == 0:
                                    i = j
                                    loop_found = True
                                    break
                                else:
                                    nest_level -= 1
                        if not loop_found:
                            self.error("EXIT DO without matching LOOP")
                    else:
                        # Re-raise for other exit types or if not in appropriate loop
                        raise

            # Check for RETURN statement. function_returned/sub_returned only
            # count as a block-exit while we're actually inside a SUB/FUNCTION
            # call (call_sub/call_function set _proc_call_depth around the
            # call) - a stray bare RETURN with no active GOSUB and outside any
            # procedure call stays the documented no-op.
            if self.return_value is not None or (
                getattr(self, '_proc_call_depth', 0) > 0 and (
                    getattr(self, 'function_returned', False) or getattr(self, 'sub_returned', False)
                )
            ):
                break

            # Handle WEND flow control
            elif statement.type == NodeType.WEND and hasattr(self, 'while_stack') and self.while_stack:
                loop_info = self.while_stack[-1]  # Get loop info before visiting
                result = self.visit(statement)

                # Check the condition to see if we should continue
                condition = self.visit(loop_info['condition_node'])

                if condition.to_single() != 0:
                    # Jump back to the statement after WHILE
                    i = loop_info['while_index']
                    continue
                else:
                    # Exit loop
                    self.while_stack.pop()

            # Handle DO statement - store the index for jumping back
            elif statement.type == NodeType.DO_LOOP:
                result = self.visit(statement)
                # DO WHILE / DO UNTIL (condition_position == 'START') is
                # pre-test: check now, before ever entering the body - this
                # used to only be checked at LOOP, so the body always ran at
                # least once even when the condition said not to (a bottom-
                # checked `DO ... LOOP WHILE/UNTIL` has no condition here and
                # is correctly unaffected - it's meant to always run once).
                if hasattr(self, 'do_stack') and self.do_stack:
                    loop_info = self.do_stack[-1]
                    if loop_info['condition_position'] == 'START' and loop_info['condition_node']:
                        condition = self.visit(loop_info['condition_node'])
                        if loop_info['condition_type'] == 'WHILE':
                            should_enter = condition.to_single() != 0
                        else:  # 'UNTIL'
                            should_enter = condition.to_single() == 0
                        if not should_enter:
                            self.do_stack.pop()
                            i = self.find_matching_loop(statements, i)
                        else:
                            loop_info['do_index'] = i + 1
                    else:
                        loop_info['do_index'] = i + 1

            # Handle LOOP flow control
            elif statement.type == NodeType.LOOP and hasattr(self, 'do_stack') and self.do_stack:
                loop_info = self.do_stack[-1]  # Get loop info before visiting
                result = self.visit(statement)

                # Check if we should continue the loop
                should_continue = True

                # Check condition from LOOP statement (end condition)
                if hasattr(statement, 'condition_position') and statement.condition_position == 'END':
                    condition = self.visit(statement.nodes[0])
                    if hasattr(statement, 'condition_type'):
                        if statement.condition_type == 'WHILE':
                            should_continue = condition.to_single() != 0
                        elif statement.condition_type == 'UNTIL':
                            should_continue = condition.to_single() == 0
                # Check condition from DO statement (start condition)
                elif loop_info['condition_position'] == 'START' and loop_info['condition_node']:
                    condition = self.visit(loop_info['condition_node'])
                    if loop_info['condition_type'] == 'WHILE':
                        should_continue = condition.to_single() != 0
                    elif loop_info['condition_type'] == 'UNTIL':
                        should_continue = condition.to_single() == 0
                # No condition means infinite loop (should continue)
                elif not loop_info['condition_node'] and not statement.nodes:
                    should_continue = True

                if should_continue:
                    # Jump back to the statement after DO
                    i = loop_info['do_index']
                    continue
                else:
                    # Exit loop
                    self.do_stack.pop()

            i += 1

        return result

    def find_matching_next(self, statements, for_index):
        """Find the index of the NEXT statement that matches the FOR at for_index"""
        nest_level = 0
        for i in range(for_index + 1, len(statements)):
            stmt = statements[i]
            if stmt.type == NodeType.FOR:
                nest_level += 1
            elif stmt.type == NodeType.NEXT:
                if nest_level == 0:
                    return i  # Return index of the NEXT statement itself
                else:
                    nest_level -= 1

        self.error("FOR without matching NEXT")

    def find_matching_wend(self, statements, while_index):
        """Find the index of the WEND statement that matches the WHILE at while_index"""
        nest_level = 0
        for i in range(while_index + 1, len(statements)):
            stmt = statements[i]
            if stmt.type == NodeType.WHILE:
                nest_level += 1
            elif stmt.type == NodeType.WEND:
                if nest_level == 0:
                    return i  # Return index of the WEND statement itself
                else:
                    nest_level -= 1

        self.error("WHILE without matching WEND")

    def find_matching_loop(self, statements, do_index):
        """Find the index of the LOOP statement that matches the DO at do_index"""
        nest_level = 0
        for i in range(do_index + 1, len(statements)):
            stmt = statements[i]
            if stmt.type == NodeType.DO_LOOP:
                nest_level += 1
            elif stmt.type == NodeType.LOOP:
                if nest_level == 0:
                    return i  # Return index of the LOOP statement itself
                else:
                    nest_level -= 1

        self.error("DO without matching LOOP")

    def execute_for_loop(self, for_node, statements, for_index):
        """Execute a complete FOR loop"""
        # Parse FOR statement
        var_node = for_node.nodes[0]
        start_expr = for_node.nodes[1]
        end_expr = for_node.nodes[2]
        step_expr = for_node.nodes[3] if len(for_node.nodes) > 3 else None

        var_name = var_node.name
        start_val = self.visit(start_expr).to_single()
        end_val = self.visit(end_expr).to_single()
        step_val = self.visit(step_expr).to_single() if step_expr else 1.0

        # Find the matching NEXT statement
        next_index = self.find_matching_next(statements, for_index)

        # Get the loop body (statements between FOR and NEXT)
        loop_body = statements[for_index + 1:next_index]

        # Initialize loop variable
        current_val = start_val

        # Execute the loop. Each iteration's body runs through visit_block
        # (the same executor as the top-level program and SUB/FUNCTION
        # bodies) instead of a hand-rolled statement walker, so a WHILE/WEND
        # or DO/LOOP nested inside a FOR actually loops (visit_block owns
        # the index-based jump-back logic those need) rather than running
        # its body exactly once. Nested FOR loops are handled the same way -
        # visit_block already dispatches NodeType.FOR to execute_for_loop -
        # so the old manual recursion here is no longer needed.
        while True:
            # Check loop condition BEFORE setting variable and executing body
            if step_val > 0:
                if current_val > end_val:
                    break
            else:
                if current_val < end_val:
                    break

            # Cooperative cancellation checkpoint
            self.check_cancelled()

            # Set loop variable
            self.variables[var_name] = Variable(current_val, 'SINGLE')

            loop_block = Node(NodeType.BLOCK, nodes=loop_body)
            try:
                self.visit(loop_block)
            except ExitException as exit_ex:
                if exit_ex.exit_type == 'FOR':
                    # Exit the FOR loop
                    return None
                # Re-raise for other exit types
                raise

            # Check for program termination (e.g. END executed in the body)
            if hasattr(self, 'program_ended') and self.program_ended:
                return None

            # Check for RETURN statement (see visit_block for why the
            # procedure-call-depth guard is needed on the flag-based forms)
            if self.return_value is not None:
                return None
            if getattr(self, '_proc_call_depth', 0) > 0 and (
                getattr(self, 'function_returned', False) or getattr(self, 'sub_returned', False)
            ):
                return None

            # Increment loop variable
            current_val += step_val

        return None

    # IF statement handling

    def visit_if(self, node):
        """Visit an IF node"""
        condition = self.visit(node.nodes[0])

        if condition.to_single() != 0:
            # Execute THEN block
            return self.visit(node.nodes[1])

        return None

    def visit_if_else(self, node):
        """Visit an IF_ELSE node"""
        condition = self.visit(node.nodes[0])

        if condition.to_single() != 0:
            # Execute THEN block
            return self.visit(node.nodes[1])
        else:
            # Check for ELSEIF clauses or ELSE block
            if len(node.nodes) > 2:
                # Check if this is an ELSEIF structure
                for i in range(2, len(node.nodes)):
                    clause = node.nodes[i]
                    if clause.type == NodeType.ELSEIF:
                        # Evaluate ELSEIF condition
                        elseif_condition = self.visit(clause.nodes[0])
                        if elseif_condition.to_single() != 0:
                            # Execute ELSEIF block
                            return self.visit(clause.nodes[1])
                    else:
                        # This is the ELSE block
                        return self.visit(clause)

        return None

    # WHILE loop handling

    def visit_while(self, node):
        """Visit a WHILE node"""
        condition_node = node.nodes[0]

        # Initialize while stack if not exists
        if not hasattr(self, 'while_stack'):
            self.while_stack = []

        # Push loop info onto stack
        loop_info = {
            'condition_node': condition_node,
            'while_index': None  # Will be set by visit_block
        }
        self.while_stack.append(loop_info)

        return None

    def visit_wend(self, _node):
        """Visit a WEND node"""
        if not hasattr(self, 'while_stack') or not self.while_stack:
            self.error("WEND without WHILE")

        # The flow control is handled in visit_block, so we don't need to do anything here
        return None

    # DO-LOOP handling

    def visit_do_loop(self, node):
        """Visit a DO_LOOP node"""
        # Initialize do stack if not exists
        if not hasattr(self, 'do_stack'):
            self.do_stack = []

        # Check for condition at start
        condition_node = None
        condition_type = None
        condition_position = 'NONE'

        if node.nodes:
            condition_node = node.nodes[0]
            condition_position = 'START'
            if hasattr(node, 'condition_type'):
                condition_type = node.condition_type

        # Push loop info onto stack
        loop_info = {
            'condition_node': condition_node,
            'condition_type': condition_type,
            'condition_position': condition_position,
            'do_index': None  # Will be set by visit_block
        }
        self.do_stack.append(loop_info)

        return None

    def visit_loop(self, _node):
        """Visit a LOOP node"""
        if not hasattr(self, 'do_stack') or not self.do_stack:
            self.error("LOOP without DO")

        # The flow control is handled in visit_block, so we don't need to do anything here
        return None

    # SELECT CASE handling

    def visit_select_case(self, node):
        """Visit a SELECT_CASE node"""
        select_expr = self.visit(node.nodes[0])

        # Evaluate each CASE clause
        for i in range(1, len(node.nodes)):
            case_node = node.nodes[i]

            if case_node.type == NodeType.CASE:
                # Check if this case matches
                case_values = case_node.nodes[0]
                case_block = case_node.nodes[1]

                if self.case_matches(select_expr, case_values):
                    return self.visit(case_block)
            else:
                # This might be an ELSE clause
                return self.visit(case_node)

        # No match found and no ELSE clause
        return None

    def visit_case(self, _node):
        """Visit a CASE node"""
        # CASE nodes are handled within visit_select_case
        # This method shouldn't be called directly
        self.error("CASE node should be handled within SELECT CASE structure")

    def case_matches(self, select_value, case_values):
        """Check if a value matches any of the case values"""
        for value_node in case_values.nodes:
            if hasattr(value_node, 'is_range') and value_node.is_range:
                # Range check (e.g., 1 TO 10)
                start_val = self.visit(value_node.nodes[0])
                end_val = self.visit(value_node.nodes[1])

                if (select_value.to_single() >= start_val.to_single() and
                    select_value.to_single() <= end_val.to_single()):
                    return True
            else:
                # Single value check
                case_val = self.visit(value_node)
                if select_value.to_single() == case_val.to_single():
                    return True

        return False

    # Control flow helpers

    def visit_elseif(self, _node):
        """Visit an ELSEIF node"""
        # ELSEIF nodes are handled within visit_if_else
        # This method shouldn't be called directly
        self.error("ELSEIF node should be handled within IF_ELSE structure")

    def visit_for(self, _node):
        """Visit a FOR node - this should not be called directly anymore"""
        # FOR loops are now handled completely by execute_for_loop in visit_block
        self.error("FOR node should be handled by execute_for_loop")

    def visit_next(self, _node):
        """Visit a NEXT node - this should not be called directly anymore"""
        # NEXT statements are now handled by execute_for_loop in visit_block
        self.error("NEXT node should be handled by execute_for_loop")

    def visit_end_if(self, _node):
        """Visit an END IF node"""
        # END IF is handled by the block structure
        return None

    def visit_end(self, _node):
        """Visit an END node"""
        # END statement terminates the program
        self.program_ended = True
        return None

    def visit_exit(self, node):
        """Visit an EXIT node"""
        # Get the exit type (FOR, WHILE, DO, etc.)
        exit_type = node.name if hasattr(node, 'name') and node.name else 'PROGRAM'

        # Raise an exception that will be caught by the appropriate loop handler
        raise ExitException(exit_type)
