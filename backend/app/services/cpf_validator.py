"""Validação de CPF por dígito verificador (algoritmo oficial, módulo 11).

Só confere se o número é matematicamente válido — não consulta nenhum
serviço externo, não confirma se o CPF existe de verdade na Receita Federal.
"""


def _check_digit(base: str) -> int:
    weights = range(len(base) + 1, 1, -1)
    total = sum(int(digit) * weight for digit, weight in zip(base, weights))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def is_valid_cpf(digits: str) -> bool:
    if len(digits) != 11 or not digits.isdigit():
        return False
    if len(set(digits)) == 1:
        # todos os dígitos iguais (000..., 111..., etc.) passam pela conta
        # mas nunca são CPFs válidos de verdade
        return False
    digit1 = _check_digit(digits[:9])
    digit2 = _check_digit(digits[:9] + str(digit1))
    return digits[9:11] == f"{digit1}{digit2}"


def validate_cpf(value: str) -> str:
    """Levanta ValueError com mensagem em português se o CPF for inválido;
    caso contrário retorna o valor original (com a formatação digitada)."""
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) != 11:
        raise ValueError("CPF deve conter 11 dígitos")
    if not is_valid_cpf(digits):
        raise ValueError("CPF inválido (dígito verificador não confere)")
    return value.strip()
