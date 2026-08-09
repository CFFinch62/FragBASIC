import pytest

from fragbasic_core.lexer import Lexer
from fragbasic_core.parser import Parser
from fragbasic_core.ast_nodes import NodeType
from fragbasic_core.errors import ParseError


def parse(code):
    tokens = Lexer(code).generate_tokens()
    return Parser(tokens).parse()


def test_parse_print():
    ast = parse('PRINT 1 + 2')
    assert ast.type == NodeType.PRINT
    assert ast.nodes[0].type == NodeType.ADD


def test_parse_if_else_single_line():
    ast = parse('IF 1 = 1 THEN PRINT "yes" ELSE PRINT "no"')
    assert ast.type == NodeType.IF_ELSE


def test_parse_for_next():
    ast = parse('FOR i = 1 TO 10\nPRINT i\nNEXT i')
    assert ast.type == NodeType.BLOCK
    assert ast.nodes[0].type == NodeType.FOR
    assert ast.nodes[-1].type == NodeType.NEXT


def test_parse_missing_then_raises_parse_error():
    with pytest.raises(ParseError) as exc_info:
        parse('IF 1 = 1 PRINT "yes"')
    assert exc_info.value.line_num == 1


def test_parse_unclosed_paren_raises_parse_error():
    with pytest.raises(ParseError):
        parse('PRINT (1 + 2')
