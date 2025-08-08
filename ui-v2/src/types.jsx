/*
 * Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * A copy of the License is located at
 *
 *   http://aws.amazon.com/apache2.0/
 *
 * or in the "license" file accompanying this file. This file is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
 * express or implied. See the License for the specific language governing
 * permissions and limitations under the License.
 */

export type WheelType = {
  wheel_id?: string;
  wheel_name: string;
  description?: string;
  participant_count?: number;
  rigging?: {
    hidden: boolean,
    participant_id: string,
  };
  created_at?: string,
  updated_at?: string,
  created_by?: string;
  settings?: {
    allow_rigging?: boolean;
    multi_select_enabled?: boolean;
    default_multi_select_count?: number;
    require_reason_for_rigging?: boolean;
    show_weights?: boolean;
    auto_reset_weights?: boolean;
  };
}

export type ParticipantType = {
  id?: string;
  name: string;
  url: string;
  wheel_id: string;
  created_at?: string;
  updated_at?: string;
}
