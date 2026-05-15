/**
 * 句级英译中（中台 §6.9），与场景包解耦。
 */

import { apiRequest } from './apiClient';

export type EnToZhResponse = {
  translated_text: string;
};

export async function postEnToZh(text: string): Promise<EnToZhResponse> {
  return apiRequest<EnToZhResponse>('POST', '/translation/en-to-zh', {
    body: { text },
  });
}
