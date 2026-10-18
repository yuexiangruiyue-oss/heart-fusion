/// 质点语言解析器 — 16质点算子管道 + 类型声明
use crate::error::{CompileError, Result};
use crate::lang::{ElementType, Sephirah, SephirahType};
use crate::lexer::{Span, Token};
use std::str::FromStr;

// ── AST ───────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub enum Expr {
    Float(f64),
    Integer(i64),
    Str(String),
    Ident(String),
    Neg(Box<Expr>),
    BinOp(BinOp, Box<Expr>, Box<Expr>),
}

#[derive(Debug, Clone, Copy)]
pub enum BinOp {
    Add, Sub, Mul, Div,
}

#[derive(Debug, Clone)]
pub enum Decl {
    Data(DataDecl),
    Const(ConstDecl),
    Pipeline(PipelineDecl),
}

#[derive(Debug, Clone)]
pub struct DataDecl {
    pub name: String,
    pub ty: SephirahType,
    pub init: Option<Expr>,
    pub span: Span,
}

#[derive(Debug, Clone)]
pub struct ConstDecl {
    pub name: String,
    pub value: Expr,
    pub span: Span,
}

#[derive(Debug, Clone)]
pub struct PipelineDecl {
    pub name: String,
    pub stages: Vec<PipelineStage>,
    pub span: Span,
}

#[derive(Debug, Clone)]
pub struct PipelineStage {
    pub opcode: Sephirah,
    pub args: Vec<String>,
    pub params: Vec<(String, Expr)>,
    pub span: Span,
}

#[derive(Debug, Clone)]
pub struct Program {
    pub decls: Vec<Decl>,
}

// ── Parser ────────────────────────────────────────────────

pub struct Parser {
    tokens: Vec<(Token, Span)>,
    pos: usize,
}

impl Parser {
    pub fn new(tokens: Vec<(Token, Span)>) -> Self {
        Self { tokens, pos: 0 }
    }

    pub fn parse(mut self) -> Result<Program> {
        let mut decls = Vec::new();
        while !self.at_eof() {
            decls.push(self.parse_decl()?);
        }
        Ok(Program { decls })
    }

    fn peek(&self) -> &Token {
        &self.tokens.get(self.pos).map(|(t, _)| t).unwrap_or(&Token::Eof)
    }

    fn peek_span(&self) -> Span {
        self.tokens.get(self.pos).map(|(_, s)| *s).unwrap_or(Span { line: 0, col: 0 })
    }

    fn advance(&mut self) -> (Token, Span) {
        let t = self.tokens.get(self.pos).cloned().unwrap_or((Token::Eof, Span { line: 0, col: 0 }));
        self.pos += 1;
        t
    }

    fn at_eof(&self) -> bool {
        matches!(self.peek(), Token::Eof)
    }

    /// Expect a specific token type
    fn expect_type(&mut self, expected_type: &str) -> Result<(Token, Span)> {
        let (tok, span) = self.advance();
        let matches = match (&tok, expected_type) {
            (Token::Ident(_), "identifier") => true,
            (Token::Integer(_), "number") => true,
            (Token::Integer(_), "dimension") => true,
            (Token::Float(_), "number") => true,
            (Token::Colon, ":") => true,
            (Token::Arrow, "→") => true,
            (Token::Eq, "=") => true,
            (Token::LParen, "(") => true,
            (Token::RParen, ")") => true,
            (Token::LBracket, "[") => true,
            (Token::RBracket, "]") => true,
            (Token::Comma, ",") => true,
            _ => false,
        };
        if matches {
            return Ok((tok, span));
        }
        let got = match &tok {
            Token::Data => "数据", Token::Pipeline => "管道", Token::Scalar => "标量",
            Token::Vector => "向量", Token::Matrix => "矩阵", Token::Tensor => "张量",
            Token::Const => "常量", Token::Colon => ":", Token::Arrow => "→",
            Token::Comma => ",", Token::Dot => ".", Token::Eq => "=",
            Token::LParen => "(", Token::RParen => ")", Token::LBracket => "[",
            Token::RBracket => "]", Token::Ident(s) => s.as_str(),
            Token::Integer(n) => &n.to_string(), Token::Float(f) => &f.to_string(),
            Token::Str(s) => s.as_str(), Token::Opcode(s) => s.keyword(),
            Token::Eof => "EOF",
            Token::Newline | Token::Comment(_) => unreachable!(),
        };
        Err(CompileError::Parse {
            line: span.line, col: span.col,
            expected: Box::leak(expected_type.to_string().into_boxed_str()),
            got: got.to_string(),
        })
    }

    fn parse_decl(&mut self) -> Result<Decl> {
        match self.peek() {
            Token::Data => {
                let span = self.peek_span();
                self.advance(); // consume 数据
                self.parse_data_decl(span)
            }
            Token::Const => {
                let span = self.peek_span();
                self.advance(); // consume 常量
                self.parse_const_decl(span)
            }
            Token::Pipeline => {
                let span = self.peek_span();
                self.advance(); // consume 管道
                self.parse_pipeline_decl(span)
            }
            Token::Opcode(_) => {
                // 匿名管道：直接以质点算子开头
                let span = self.peek_span();
                self.parse_anon_pipeline(span)
            }
            tok => Err(CompileError::Parse {
                line: self.peek_span().line,
                col: self.peek_span().col,
                expected: "数据 / 管道 / 质点算子",
                got: format!("{:?}", tok),
            }),
        }
    }

    fn parse_data_decl(&mut self, span: Span) -> Result<Decl> {
        let (name_tok, _) = self.expect_type("identifier")?;
        let name = match name_tok {
            Token::Ident(s) => s,
            _ => return Err(CompileError::Parse {
                line: self.peek_span().line, col: self.peek_span().col,
                expected: "标识符", got: format!("{:?}", name_tok),
            }),
        };

        self.expect_type(":")?;
        let ty = self.parse_type()?;
        let init = if matches!(self.peek(), Token::Eq) {
            self.advance();
            Some(self.parse_expr()?)
        } else {
            None
        };

        Ok(Decl::Data(DataDecl { name, ty, init, span }))
    }

    fn parse_const_decl(&mut self, span: Span) -> Result<Decl> {
        let (name_tok, name_span) = self.advance();
        let name = match name_tok {
            Token::Ident(s) => s,
            _ => return Err(CompileError::Parse {
                line: name_span.line, col: name_span.col,
                expected: "标识符", got: format!("{:?}", name_tok),
            }),
        };
        self.expect_type("=")?;
        let value = self.parse_expr()?;
        Ok(Decl::Const(ConstDecl { name, value, span }))
    }

    fn parse_pipeline_decl(&mut self, span: Span) -> Result<Decl> {
        let (name_tok, name_span) = self.advance();
        let name = match name_tok {
            Token::Ident(s) => s,
            _ => return Err(CompileError::Parse {
                line: name_span.line, col: name_span.col,
                expected: "管道名", got: format!("{:?}", name_tok),
            }),
        };
        self.expect_type(":")?;

        let mut stages = Vec::new();
        stages.push(self.parse_stage()?);

        while matches!(self.peek(), Token::Arrow) {
            self.advance(); // consume →
            stages.push(self.parse_stage()?);
        }

        Ok(Decl::Pipeline(PipelineDecl { name, stages, span }))
    }

    fn parse_anon_pipeline(&mut self, span: Span) -> Result<Decl> {
        let mut stages = Vec::new();
        stages.push(self.parse_stage()?);

        while matches!(self.peek(), Token::Arrow) {
            self.advance();
            stages.push(self.parse_stage()?);
        }

        Ok(Decl::Pipeline(PipelineDecl {
            name: "main".into(),
            stages,
            span,
        }))
    }

    fn parse_stage(&mut self) -> Result<PipelineStage> {
        let span = self.peek_span();
        let (tok, tok_span) = self.advance();

        let opcode = match tok {
            Token::Opcode(op) => op,
            _ => return Err(CompileError::Parse {
                line: tok_span.line, col: tok_span.col,
                expected: "质点算子 (王冠/智慧/.../王国)",
                got: format!("{:?}", tok),
            }),
        };

        // 参数括号可选
        let mut args = Vec::new();
        if matches!(self.peek(), Token::LParen) {
        self.expect_type("(")?;
        if !matches!(self.peek(), Token::RParen) {
            let (arg_tok, arg_span) = self.advance();
            let arg = match arg_tok {
                Token::Ident(s) => s,
                Token::Opcode(op) => op.keyword().to_string(),
                Token::Float(f) => f.to_string(),
                Token::Integer(n) => n.to_string(),
                _ => return Err(CompileError::Parse {
                    line: arg_span.line, col: arg_span.col,
                    expected: "参数名", got: format!("{:?}", arg_tok),
                }),
            };
            args.push(arg);
            while matches!(self.peek(), Token::Comma) {
                self.advance();
                let (a, _) = self.advance();
                match a {
                    Token::Ident(s) => args.push(s),
                    Token::Opcode(op) => args.push(op.keyword().to_string()),
                    Token::Float(f) => args.push(f.to_string()),
                    Token::Integer(n) => args.push(n.to_string()),
                    _ => args.push(format!("{:?}", a)),
                }
            }
        }
        self.expect_type(")")?;
        } // end if LParen

        // 可选参数 [...]
        let mut params = Vec::new();
        if matches!(self.peek(), Token::LBracket) {
            self.advance();
            if !matches!(self.peek(), Token::RBracket) {
                let (key_tok, key_span) = self.advance();
                let key = match key_tok {
                    Token::Ident(s) => s,
                    _ => return Err(CompileError::Parse {
                        line: key_span.line, col: key_span.col,
                        expected: "参数名", got: format!("{:?}", key_tok),
                    }),
                };
                self.expect_type(":")?;
                let val = self.parse_expr()?;
                params.push((key, val));
                while matches!(self.peek(), Token::Comma) {
                    self.advance();
                    let (k, ks) = self.advance();
                    let key = match k {
                        Token::Ident(s) => s,
                        _ => return Err(CompileError::Parse {
                            line: ks.line, col: ks.col,
                            expected: "参数名", got: format!("{:?}", k),
                        }),
                    };
                    self.expect_type(":")?;
                    let val = self.parse_expr()?;
                    params.push((key, val));
                }
            }
            self.expect_type("]")?;
        }

        Ok(PipelineStage { opcode, args, params, span })
    }

    fn parse_type(&mut self) -> Result<SephirahType> {
        let (tok, span) = self.advance();
        match tok {
            Token::Scalar => {
                let et = self.parse_element_type()?;
                Ok(SephirahType::Scalar(et))
            }
            Token::Vector => {
                self.expect_type("[")?;
                let (dim_tok, _) = self.expect_type("dimension")?;
                let dim = match dim_tok {
                    Token::Integer(n) => n as usize,
                    _ => return Err(CompileError::Parse {
                        line: span.line, col: span.col,
                        expected: "维度数", got: format!("{:?}", dim_tok),
                    }),
                };
                self.expect_type(",")?;
                let et = self.parse_element_type()?;
                self.expect_type("]")?;
                Ok(SephirahType::Vector(dim, et))
            }
            Token::Matrix => {
                self.expect_type("[")?;
                let (rows_tok, _) = self.advance();
                let rows = match rows_tok {
                    Token::Integer(n) => n as usize,
                    _ => return Err(CompileError::Parse {
                        line: span.line, col: span.col,
                        expected: "行数", got: format!("{:?}", rows_tok),
                    }),
                };
                self.expect_type(",")?;
                let (cols_tok, _) = self.advance();
                let cols = match cols_tok {
                    Token::Integer(n) => n as usize,
                    _ => return Err(CompileError::Parse {
                        line: span.line, col: span.col,
                        expected: "列数", got: format!("{:?}", cols_tok),
                    }),
                };
                self.expect_type(",")?;
                let et = self.parse_element_type()?;
                self.expect_type("]")?;
                Ok(SephirahType::Matrix(rows, cols, et))
            }
            Token::Tensor => {
                self.expect_type("[")?;
                let mut dims = Vec::new();
                let (d_tok, _) = self.advance();
                match d_tok {
                    Token::Integer(n) => dims.push(n as usize),
                    _ => return Err(CompileError::Parse {
                        line: span.line, col: span.col,
                        expected: "维度", got: format!("{:?}", d_tok),
                    }),
                }
                while matches!(self.peek(), Token::Comma) {
                    self.advance();
                    if matches!(self.peek(), Token::Ident(_)) {
                        break; // this is the element type
                    }
                    let (d, _) = self.advance();
                    match d {
                        Token::Integer(n) => dims.push(n as usize),
                        _ => break,
                    }
                }
                self.expect_type(",")?;
                let et = self.parse_element_type()?;
                self.expect_type("]")?;
                Ok(SephirahType::Tensor(dims, et))
            }
            _ => Err(CompileError::Parse {
                line: span.line, col: span.col,
                expected: "类型 (标量/向量/矩阵/张量)",
                got: format!("{:?}", tok),
            }),
        }
    }

    fn parse_element_type(&mut self) -> Result<ElementType> {
        let (tok, span) = self.advance();
        match &tok {
            Token::Ident(s) => {
                ElementType::from_str(s).map_err(|_| CompileError::Parse {
                    line: span.line, col: span.col,
                    expected: "元素类型 (f16/bf16/f32/f64/i8/i16/i32/i64/u8/u16/u32/u64)",
                    got: s.clone(),
                })
            }
            _ => Err(CompileError::Parse {
                line: span.line, col: span.col,
                expected: "元素类型", got: format!("{:?}", tok),
            }),
        }
    }

    fn parse_expr(&mut self) -> Result<Expr> {
        self.parse_additive()
    }

    fn parse_additive(&mut self) -> Result<Expr> {
        let mut left = self.parse_multiplicative()?;
        loop {
            let (tok, _span) = if self.pos < self.tokens.len() {
                (self.tokens[self.pos].0.clone(), self.tokens[self.pos].1)
            } else {
                break;
            };
            match tok {
                Token::Ident(s) if s == "+" => {
                    self.advance();
                    let right = self.parse_multiplicative()?;
                    left = Expr::BinOp(BinOp::Add, Box::new(left), Box::new(right));
                }
                Token::Ident(s) if s == "-" => {
                    self.advance();
                    let right = self.parse_multiplicative()?;
                    left = Expr::BinOp(BinOp::Sub, Box::new(left), Box::new(right));
                }
                _ => break,
            }
        }
        Ok(left)
    }

    fn parse_multiplicative(&mut self) -> Result<Expr> {
        let mut left = self.parse_unary()?;
        loop {
            let tok = self.peek().clone();
            match tok {
                Token::Ident(s) if s == "*" => {
                    self.advance();
                    let right = self.parse_unary()?;
                    left = Expr::BinOp(BinOp::Mul, Box::new(left), Box::new(right));
                }
                Token::Ident(s) if s == "/" => {
                    self.advance();
                    let right = self.parse_unary()?;
                    left = Expr::BinOp(BinOp::Div, Box::new(left), Box::new(right));
                }
                _ => break,
            }
        }
        Ok(left)
    }

    fn parse_unary(&mut self) -> Result<Expr> {
        match self.peek() {
            Token::Ident(s) if s == "负" || s == "-" => {
                self.advance();
                let inner = self.parse_primary()?;
                Ok(Expr::Neg(Box::new(inner)))
            }
            _ => self.parse_primary(),
        }
    }

    fn parse_primary(&mut self) -> Result<Expr> {
        let (tok, span) = self.advance();
        match tok {
            Token::Float(f) => Ok(Expr::Float(f)),
            Token::Integer(n) => Ok(Expr::Integer(n)),
            Token::Str(s) => Ok(Expr::Str(s)),
            Token::Ident(s) => Ok(Expr::Ident(s)),
            Token::Opcode(op) => Ok(Expr::Ident(op.keyword().to_string())),
            Token::LParen => {
                let inner = self.parse_expr()?;
                self.expect_type(")")?;
                Ok(inner)
            }
            _ => Err(CompileError::Parse {
                line: span.line, col: span.col,
                expected: "表达式",
                got: format!("{:?}", tok),
            }),
        }
    }
}

/// 便捷：解析源码字符串
pub fn parse(source: &str) -> Result<Program> {
    let tokens = crate::lexer::tokenize(source)?;
    Parser::new(tokens).parse()
}
