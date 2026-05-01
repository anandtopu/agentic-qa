// SDK error hierarchy mirroring HTTP status codes.

export class AQAOError extends Error {
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

export class AuthError extends AQAOError {}
export class ForbiddenError extends AQAOError {}
export class NotFoundError extends AQAOError {}
export class ConflictError extends AQAOError {}
export class ValidationError extends AQAOError {}
export class RateLimitError extends AQAOError {
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

const STATUS_TO_ERROR: Record<number, new (...args: ConstructorParameters<typeof AQAOError>) => AQAOError> = {
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
}): AQAOError {
  const { statusCode, message, traceId, details = [], retryAfterSeconds } = args;
  if (statusCode === 429) {
    return new RateLimitError(message, statusCode, traceId, details, retryAfterSeconds);
  }
  const Cls = STATUS_TO_ERROR[statusCode];
  if (Cls !== undefined) {
    return new Cls(message, statusCode, traceId, details);
  }
  return new AQAOError(message, statusCode, traceId, details);
}
