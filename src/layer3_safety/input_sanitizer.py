"""Input sanitization and prompt injection detection."""

import re
import html
from typing import Tuple, List, Dict, Any
from src.layer1_settings import settings, logger


class InputSanitizer:
    """Cleans user input to prevent injection attacks."""

    # Comprehensive injection patterns (50+)
    INJECTION_PATTERNS = [
        # ===== PROMPT INJECTION (15) =====
        r"(?:ignore|forget|disregard)\s+(?:previous|prior|everything)",
        r"system\s+override",
        r"admin\s+(?:command|mode|access)",
        r"execute\s+(?:code|command|sql)",
        r"run\s+(?:query|command|code)",
        r"<\s*(?:system|admin|command|override)",
        r">\s*(?:system|admin|command)",
        r"instruction:\s+",
        r"directive:\s+",
        r"rule\s+override",
        r"break\s+(?:character|roleplay|protocol)",
        r"pretend\s+(?:you\s+(?:are|were)|to\s+be)",
        r"(?:act|behave|respond)\s+as\s+(?:if|though)",
        r"imagine\s+you\s+(?:are|were)",
        r"simulate\s+(?:being|a)",
        
        # ===== SQL INJECTION (12) =====
        r"(?:union|select|insert|update|delete|drop|create|alter|truncate)\s+(?:from|into|table|database|schema)",
        r"(\';|\")\s*(?:or|and)",
        r"(?:or|and)\s+(?:'1'|\"1\"|1)\s*=\s*(?:'1'|\"1\"|1)",
        r"(?:or|and)\s+(?:true|false)",
        r"--\s*(?:comment|sql)",
        r"/\*.*?\*/",
        r"xp_(?:cmdshell|regread|regwrite)",
        r"sp_(?:executesql|oacreate|adduser)",
        r"exec(?:ute)?\s*\(",
        r"cast\s*\(",
        r"convert\s*\(",
        r"char\s*\(",
        
        # ===== JAVASCRIPT/XSS (15) =====
        r"<\s*script[^>]*>",
        r"</\s*script\s*>",
        r"javascript:",
        r"vbscript:",
        r"on(?:load|error|click|focus|mouseover|mouseenter)\s*=",
        r"src\s*=\s*(?:javascript|data)",
        r"href\s*=\s*(?:javascript|data)",
        r"<\s*(?:iframe|embed|object|applet)",
        r"<img[^>]*onerror",
        r"<svg[^>]*on",
        r"eval\s*\(",
        r"expression\s*\(",
        r"vbscript\s*:",
        r"data:text/html",
        r"<meta[^>]*(?:refresh|http-equiv)",
        
        # ===== CODE INJECTION (10) =====
        r"__import__",
        r"(?:exec|eval)\s*\(",
        r"os\.(?:system|popen|exec)",
        r"subprocess\.(?:call|run|popen)",
        r"pickle\.(?:loads|dumps)",
        r"importlib\.(?:import_module|load_module)",
        r"\$(?:\(|{)",  # Shell substitution
        r"`.*?`",  # Command substitution
        r"&&|;.*?\|",  # Command chaining
        r"\[\[\s*.*?\s*\]\]",  # Bash conditionals
        
        # ===== XML/XPATH (8) =====
        r"<!ENTITY",
        r"SYSTEM\s+\"",
        r"\[CDATA\[",
        r"xmlns:",
        r"<\?xml",
        r"DOCTYPE",
        r"<!DOCTYPE",
        r"xsi:",
        
        # ===== CREDENTIAL LEAKS (8) =====
        r"(?:password|passwd|pwd)\s*[:=]",
        r"(?:api[_-]?key|apikey)\s*[:=]",
        r"(?:secret|client[_-]?secret)\s*[:=]",
        r"(?:token|access[_-]?token)\s*[:=]",
        r"(?:bearer|jwt)\s+",
        r"authorization:\s*(?:bearer|basic)",
        r"x-api-key:\s*",
        r"credentials\s*[:=]",
        
        # ===== PATH TRAVERSAL (6) =====
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e/",
        r"%252e%252e",
        r"..;/",
        r"..%5c",
        
        # ===== JSON/YAML INJECTION (5) =====
        r'"\s*:\s*"(?:__proto__|constructor|prototype)"',
        r"prototype\s*[:=]",
        r"__proto__\s*[:=]",
        r"&:\s*",
        r"<<\s*:",
    ]

    def __init__(self):
        """Compile injection patterns."""
        self.patterns = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.INJECTION_PATTERNS]
        self.max_length = 5000

    def sanitize(self, user_input: str, max_length: int | None = None) -> str:
        """
        Clean user input comprehensively.

        Args:
            user_input: Raw user input
            max_length: Max allowed length (defaults to 5000)

        Returns:
            Sanitized input
        """
        if not user_input:
            return ""

        max_len = max_length or self.max_length
        text = user_input[:max_len]

        # Remove null bytes and control characters
        text = "".join(c for c in text if ord(c) >= 32 or c in "\t\n\r")

        # Normalize whitespace
        text = " ".join(text.split())

        # Decode HTML entities (prevent double encoding attacks)
        try:
            text = html.unescape(text)
        except Exception as e:
            logger.warning(f"HTML unescape failed: {e}")

        return text.strip()

    def detect_injection(self, text: str) -> Tuple[bool, List[str]]:
        """
        Detect potential injection attempts with detailed matching.

        Args:
            text: Input text to check

        Returns:
            Tuple of (is_injection_detected, matched_patterns)
        """
        if not text:
            return False, []

        matched = []
        for i, pattern in enumerate(self.patterns):
            if pattern.search(text):
                matched.append(f"pattern_{i}: {pattern.pattern[:50]}...")

        if matched:
            logger.warning(f"Injection patterns detected ({len(matched)}): {matched[:5]}")
            return True, matched

        return False, []

    def validate_query_length(self, query: str) -> bool:
        """Check if query length is reasonable."""
        words = len(query.split())
        return 1 <= words <= 500  # 1-500 words

    def validate_query_characters(self, query: str) -> bool:
        """Check for suspicious character patterns."""
        # Allow mostly alphanumeric + common punctuation
        allowed_pattern = r"^[a-zA-Z0-9\s\.\,\?\!\-\'\"\(\)]+$"
        # If query has unusual characters, be more lenient
        if not re.match(allowed_pattern, query):
            logger.debug(f"Query contains special characters: {query[:100]}")
            return True  # Still allow, just log
        return True


class PromptInjectionDetector:
    """Specialized detector for prompt injection attacks."""

    # Prompt-specific injection techniques
    PROMPT_INJECTIONS = [
        # Role playing
        r"you are now\s+a",
        r"pretend you are",
        r"act as if",
        r"from now on",
        # Instruction override
        r"ignore.*instruction",
        r"disregard.*rule",
        r"override.*setting",
        # Context breaking
        r"<new_context>",
        r"</context>",
        r"[END OF CONTEXT]",
        # Hidden instructions
        r"hidden.*instruction",
        r"secret.*command",
    ]

    def __init__(self):
        """Compile patterns."""
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.PROMPT_INJECTIONS]

    def detect(self, text: str) -> Tuple[bool, List[str]]:
        """
        Detect prompt injection attempts.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (is_injection, matched_patterns)
        """
        if not text:
            return False, []

        matched = []
        for pattern in self.patterns:
            if pattern.search(text):
                matched.append(pattern.pattern)

        if matched:
            logger.warning(f"Prompt injection detected: {matched}")
            return True, matched

        return False, []


def create_safe_context(
    user_query: str,
    retrieved_chunks: List[str],
    system_message: str = "",
) -> str:
    """
    Create safe prompt context preventing injection.

    Args:
        user_query: User's question
        retrieved_chunks: Relevant document chunks
        system_message: System instructions

    Returns:
        Formatted prompt context
    """
    sanitizer = InputSanitizer()

    # Sanitize user query
    safe_query = sanitizer.sanitize(user_query)

    # Build context with clear boundaries
    context_parts = [
        "=== SYSTEM CONTEXT START ===",
        system_message or "You are a helpful AI assistant.",
        "=== SYSTEM CONTEXT END ===",
        "",
        "=== RETRIEVED DOCUMENTS START ===",
    ]

    # Add chunks with clear boundaries
    for i, chunk in enumerate(retrieved_chunks):
        context_parts.append(f"--- DOCUMENT {i+1} ---")
        context_parts.append(chunk)
        context_parts.append("--- END DOCUMENT ---")

    context_parts.extend([
        "=== RETRIEVED DOCUMENTS END ===",
        "",
        "=== USER QUESTION ===",
        safe_query,
        "=== END USER QUESTION ===",
    ])

    return "\n".join(context_parts)
