// SDK error hierarchy mirroring HTTP status codes.

export class QAForgeError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number | undefined,
    public readonly traceId: string | undefined,
    public readonly details: ReadonlyArray<Record<string, unknown>> = [],
  ) {
    super(message);
    this.name = new.target.name;
  }
}

export class AuthError extends QAForgeError {}
export class ForbiddenError extends QAForgeError {}
export class NotFoundError extends QAForgeError {}
export class ConflictError extends QAForgeError {}
export class ValidationError extends QAForgeError {}
export class RateLimitError extends QAForgeError {
  constructor(
    message: string,
    statusCode: number | undefined,
    traceId: string | undefined,
    details: ReadonlyArray<Record<string, unknown>>,
    public readonly retryAfterSeconds: number | undefined,
  ) {
    super(message, statusCode, traceId, details);
  }
}

const STATUS_TO_ERROR: Record<number, new (...args: ConstructorParameters<typeof QAForgeError>) => QAForgeError> = {
  401: AuthError,
  403: ForbiddenError,
  404: NotFoundError,
  409: ConflictError,
  422: ValidationError,
};

export function errorForStatus(args: {
  statusCode: number;
  message: string;
  traceId?: string | undefined;
  details?: ReadonlyArray<Record<string, unknown>>;
  retryAfterSeconds?: number | undefined;
}): QAForgeError {
  const { statusCode, message, traceId, details = [], retryAfterSeconds } = args;
  if (statusCode === 429) {
    return new RateLimitError(message, statusCode, traceId, details, retryAfterSeconds);
  }
  const Cls = STATUS_TO_ERROR[statusCode];
  if (Cls !== undefined) {
    return new Cls(message, statusCode, traceId, details);
  }
  return new QAForgeError(message, statusCode, traceId, details);
}
