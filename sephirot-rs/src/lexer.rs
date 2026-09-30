/// 质点语言词法分析器 — UTF-8安全的中文源码扫描
use crate::error::{CompileError, Result};
use crate::lang::{ElementType, Sephirah};
use std::str::FromStr;

/// 词法单元
#[derive(Debug, Clone, PartialEq)]
pub enum Token {
    // 关键字
    Data,       // 数据
    Pipeline,   // 管道
    Scalar,     // 标量
    Vector,     // 向量
    Matrix,     // 矩阵
    Tensor,     // 张量
    Const,      // 常量

    // 16质点算子
    Opcode(Sephirah),

    // 字面量
    Float(f64),
    Integer(i64),
    Str(String),
    Ident(String),

    // 标点
    Colon,      // :
    Arrow,      // →
    Comma,      // ,
    Dot,        // .
    Eq,         // =
    LParen,     // (
    RParen,     // )
    LBracket,   // [
    RBracket,   // ]

    // 控制
    Newline,
    Comment(String),
    Eof,
}

impl Token {
    pub fn is_newline_or_comment(&self) -> bool {
        matches!(self, Token::Newline | Token::Comment(_))
    }
}

/// 源码位置
#[derive(Debug, Clone, Copy)]
pub struct Span {
    pub line: usize,
    pub col: usize,
}

/// 词法分析器
pub struct Lexer {
    bytes: Vec<u8>,
    pos: usize,
    line: usize,
    col: usize,
    tokens: Vec<(Token, Span)>,
}

impl Lexer {
    pub fn new(source: &str) -> Self {
        Self {
            bytes: source.as_bytes().to_vec(),
            pos: 0,
            line: 1,
            col: 1,
            tokens: Vec::new(),
        }
    }

    pub fn tokenize(&mut self) -> Result<Vec<(Token, Span)>> {
        while self.pos < self.bytes.len() {
            self.skip_whitespace_and_comments();
            if self.pos >= self.bytes.len() {
                break;
            }
            let span = Span { line: self.line, col: self.col };
            let tok = self.next_token()?;
            self.tokens.push((tok, span));
        }
        self.tokens.push((Token::Eof, Span { line: self.line, col: self.col }));
        Ok(std::mem::take(&mut self.tokens))
    }

    fn peek(&self) -> u8 {
        self.bytes.get(self.pos).copied().unwrap_or(0)
    }

    fn peek2(&self) -> u8 {
        self.bytes.get(self.pos + 1).copied().unwrap_or(0)
    }

    fn advance(&mut self) -> u8 {
        let b = self.bytes[self.pos];
        self.pos += 1;
        if b == b'\n' {
            self.line += 1;
            self.col = 1;
        } else {
            self.col += 1;
        }
        b
    }

    fn skip_whitespace_and_comments(&mut self) {
        while self.pos < self.bytes.len() {
            match self.peek() {
                b' ' | b'\t' | b'\r' => { self.advance(); }
                b'\n' => { self.advance(); } // skip newlines
                b'#' => {
                    self.advance(); // skip #
                    while self.pos < self.bytes.len() && self.peek() != b'\n' {
                        self.advance(); // skip comment content
                    }
                }
                _ => break,
            }
        }
    }

    fn read_utf8_char(&mut self) -> Result<char> {
        let b = self.peek();
        let ch = if b < 0x80 {
            let c = b as char;
            self.advance();
            c
        } else {
            // Determine UTF-8 byte length from leading byte
            let byte_len = if b >= 0xF0 { 4 } else if b >= 0xE0 { 3 } else { 2 };
            let end = std::cmp::min(self.pos + byte_len, self.bytes.len());
            let s = &self.bytes[self.pos..end];
            let ch = std::str::from_utf8(s)
                .ok()
                .and_then(|s| s.chars().next())
                .ok_or_else(|| CompileError::Lex {
                    line: self.line,
                    col: self.col,
                    msg: "无效的UTF-8编码".into(),
                })?;
            for _ in 0..ch.len_utf8() {
                self.advance();
            }
            ch
        };
        Ok(ch)
    }

    fn read_number(&mut self, first_digit: u8) -> Result<Token> {
        let mut num_str = String::new();
        num_str.push(first_digit as char);
        let mut is_float = false;

        while self.pos < self.bytes.len() {
            let b = self.peek();
            if b.is_ascii_digit() {
                num_str.push(self.advance() as char);
            } else if b == b'.' && !is_float {
                is_float = true;
                num_str.push(self.advance() as char);
            } else {
                break;
            }
        }

        if is_float {
            num_str.parse::<f64>()
                .map(Token::Float)
                .map_err(|e| CompileError::Lex {
                    line: self.line, col: self.col,
                    msg: format!("无效浮点数: {}", e),
                })
        } else {
            num_str.parse::<i64>()
                .map(Token::Integer)
                .map_err(|e| CompileError::Lex {
                    line: self.line, col: self.col,
                    msg: format!("无效整数: {}", e),
                })
        }
    }

    fn read_string(&mut self) -> Result<Token> {
        self.advance(); // skip opening "
        let mut s = String::new();
        while self.pos < self.bytes.len() && self.peek() != b'"' {
            if self.peek() == b'\\' {
                self.advance();
                match self.peek() {
                    b'n' => { self.advance(); s.push('\n'); }
                    b't' => { self.advance(); s.push('\t'); }
                    b'"' => { self.advance(); s.push('"'); }
                    b'\\' => { self.advance(); s.push('\\'); }
                    _ => {
                        let ch = self.read_utf8_char()?;
                        s.push(ch);
                    }
                }
            } else {
                let ch = self.read_utf8_char()?;
                s.push(ch);
            }
        }
        if self.pos >= self.bytes.len() {
            return Err(CompileError::Lex {
                line: self.line, col: self.col,
                msg: "字符串未闭合".into(),
            });
        }
        self.advance(); // skip closing "
        Ok(Token::Str(s))
    }

    fn read_ident_or_keyword(&mut self, first_char: char) -> Result<Token> {
        let mut word = String::new();
        word.push(first_char);

        while self.pos < self.bytes.len() {
            let b = self.peek();
            if b.is_ascii_alphanumeric() || b == b'_' || b >= 0x80 {
                let ch = self.read_utf8_char()?;
                word.push(ch);
            } else {
                break;
            }
        }

        // 检查是否为质点算子
        if let Ok(op) = Sephirah::from_str(word.as_str()) {
            return Ok(Token::Opcode(op));
        }

        // 检查是否为关键字
        match word.as_str() {
            "数据" => Ok(Token::Data),
            "管道" => Ok(Token::Pipeline),
            "标量" => Ok(Token::Scalar),
            "向量" => Ok(Token::Vector),
            "矩阵" => Ok(Token::Matrix),
            "张量" => Ok(Token::Tensor),
            "常量" => Ok(Token::Const),
            _ => Ok(Token::Ident(word)),
        }
    }

    fn next_token(&mut self) -> Result<Token> {
        let b = self.peek();

        // ASCII 符号
        match b {
            b':' => { self.advance(); Ok(Token::Colon) }
            b',' => { self.advance(); Ok(Token::Comma) }
            b'.' => { self.advance(); Ok(Token::Dot) }
            b'=' => { self.advance(); Ok(Token::Eq) }
            b'(' => { self.advance(); Ok(Token::LParen) }
            b')' => { self.advance(); Ok(Token::RParen) }
            b'[' => { self.advance(); Ok(Token::LBracket) }
            b']' => { self.advance(); Ok(Token::RBracket) }
            b'"' => self.read_string(),
            b'0'..=b'9' => {
                self.advance();
                self.read_number(b)
            }
            b'-' if self.peek2() == b'>' => {
                // → or ->
                // Check for actual → (UTF-8 0xE2 0x86 0x92)
                // This branch handles ASCII ->
                self.advance(); // -
                self.advance(); // >
                Ok(Token::Arrow)
            }
            _ if b >= 0x80 => {
                // 可能是 → (U+2192) 或中文关键字
                let ch = self.read_utf8_char()?;
                if ch == '\u{2192}' {
                    return Ok(Token::Arrow);
                }
                self.read_ident_or_keyword(ch)
            }
            b'a'..=b'z' | b'A'..=b'Z' | b'_' => {
                self.advance();
                self.read_ident_or_keyword(b as char)
            }
            _ => Err(CompileError::Lex {
                line: self.line, col: self.col,
                msg: format!("未知字符: '{}' (U+{:04X})", b as char, b),
            }),
        }
    }
}

/// 便捷函数：直接词法分析
pub fn tokenize(source: &str) -> Result<Vec<(Token, Span)>> {
    Lexer::new(source).tokenize()
}

/// 元素类型词法解析
pub fn parse_element_type(s: &str) -> Option<ElementType> {
    ElementType::from_str(s).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_tokens() {
        let src = "数据 输入 : 标量 f32";
        let toks = tokenize(src).unwrap();
        assert_eq!(toks[0].0, Token::Data);
        assert_eq!(toks[1].0, Token::Ident("输入".into()));
        assert_eq!(toks[2].0, Token::Colon);
        assert_eq!(toks[3].0, Token::Scalar);
        assert_eq!(toks[4].0, Token::Ident("f32".into()));
    }

    #[test]
    fn test_opcodes() {
        let src = "王冠(输入) → 智慧(知识库)";
        let toks = tokenize(src).unwrap();
        assert_eq!(toks[0].0, Token::Opcode(Sephirah::王冠));
        assert_eq!(toks[1].0, Token::LParen);
        assert_eq!(toks[2].0, Token::Ident("输入".into()));
        assert_eq!(toks[4].0, Token::Arrow);
        assert_eq!(toks[5].0, Token::Opcode(Sephirah::智慧));
    }

    #[test]
    fn test_arrow_variants() {
        let toks1 = tokenize("→").unwrap();
        assert_eq!(toks1[0].0, Token::Arrow);
        let toks2 = tokenize("->").unwrap();
        assert_eq!(toks2[0].0, Token::Arrow);
    }
}
