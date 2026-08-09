import pytest

from fragbasic_core.lexer import Lexer
from fragbasic_core.tokens import TokenType
from fragbasic_core.errors import LexerError


def token_types(code):
    return [t.type for t in Lexer(code).generate_tokens()]


def test_simple_print():
    tokens = Lexer('PRINT "hi"').generate_tokens()
    assert tokens[0].type == TokenType.KEYWORD
    assert tokens[0].name == 'PRINT'
    assert tokens[1].type == TokenType.STRING
    assert tokens[1].name == 'hi'


def test_number_with_suffix():
    tokens = Lexer('5%').generate_tokens()
    assert tokens[0].type == TokenType.NUMBER
    assert tokens[0].value == 5


def test_operators():
    types = token_types('1 <= 2 <> 3 >= 4')
    assert TokenType.LTE in types
    assert TokenType.NE in types
    assert TokenType.GTE in types


def test_line_tracking():
    tokens = Lexer('PRINT 1\nPRINT 2').generate_tokens()
    line_nums = [t.line_num for t in tokens if t.type == TokenType.NUMBER]
    assert line_nums == [1, 2]


def test_illegal_character_raises_lexer_error():
    with pytest.raises(LexerError) as exc_info:
        Lexer('PRINT @').generate_tokens()
    assert exc_info.value.line_num == 1


def test_unterminated_string_raises_lexer_error():
    with pytest.raises(LexerError):
        Lexer('PRINT "unterminated').generate_tokens()


def test_rem_comment_consumes_rest_of_line():
    tokens = Lexer('REM this is a comment\nPRINT 1').generate_tokens()
    keyword_names = [t.name for t in tokens if t.type == TokenType.KEYWORD]
    assert keyword_names == ['REM', 'PRINT']
