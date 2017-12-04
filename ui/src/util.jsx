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

import React, {Component} from 'react';
import moment from 'moment';
import * as moment_tz from 'moment-timezone';
import {Link} from 'react-router-dom';

export const DATE_FORMAT: string = 'YYYY-MM-DD HH:mm:ss';
export function formatDateTime(timestamp: string, withTimeZone: boolean) {
    if (withTimeZone) {
        const dateTimeFormat = 'YYYY-MM-DD HH:mm:ss z';
        return moment_tz.tz(timestamp, moment_tz.tz.guess()).format(dateTimeFormat);
    } else {
        return moment(timestamp).format(DATE_FORMAT);
    }
}

export const WHEEL_COLORS = [
    '#FF9900',
    '#007dbc',
    '#ec7211',
    '#FFFFFF',
    '#6aaf35',
    '#aab7b8',
    '#df3312',
    '#545b64',
    '#eaeded',
    '#eb5f07',
    '#FAFAFA',
    '#00a1c9',
    '#F2F4F4',
    '#1e8900',
    '#d5dbdb',
    '#ff5746',
];

// Testing URLs need to be absolute
export const apiURL = (urlSuffix) => {
  const urlPrefix = (process.env.NODE_ENV === 'test') ? 'http://localhost' : '';
  return (`${urlPrefix}/app/api/${urlSuffix}`);
};

export const staticURL = (urlSuffix) => {
  const urlPrefix = (process.env.NODE_ENV === 'test') ? 'http://localhost' : '';
  return (`${urlPrefix}/app/static/${urlSuffix}`);
};

/* This is a wrapper around Link to disable Links while testing and apply a local route prefix.
   <Link> cannot exist outside of a router context (it triggers an Invariant), but creating a router
   context makes it very difficult to access the internals of the object via enzyme as it is wrapped by the
   <Router>.
*/
export class LinkWrapper extends Component {
  render () {
    let link: any;
    let props: Object = Object.assign({}, this.props);

    if (props.remote !== true)
      props.to = `/app/${props.to}`;

    if ('remote' in props)
      delete props.remote;

    if (process.env.NODE_ENV === 'test')
      link = <div> {props.to}`} {props.children} </div>;
    else
      /* istanbul ignore next */
      link = <Link {...props}>{props.children}</Link>;

    return (
      <div>
        {link}
      </div>
    );
  }
}
