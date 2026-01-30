import { z } from "zod";

/**
 * AVM (Algorand) exact scheme payload structure
 */
export const ExactAvmPayloadSchema = z.object({
  paymentGroup: z.array(z.string()), // Base64-encoded msgpack transactions
  paymentIndex: z.number().int().nonnegative(), // Index of payment transaction
});

export type ExactAvmPayload = z.infer<typeof ExactAvmPayloadSchema>;

/**
 * Type guard for ExactAvmPayload
 */
export function isExactAvmPayload(payload: unknown): payload is ExactAvmPayload {
  return ExactAvmPayloadSchema.safeParse(payload).success;
}
