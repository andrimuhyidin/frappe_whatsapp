frappe.pages['setup-wizard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Setup Wizard'),
		single_column: true
	});

	new SetupWizard(wrapper);
}

class SetupWizard {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.init();
	}

	init() {
		this.render_container();
		this.current_step = 0;
		this.steps = [
			{
				title: __('Indonesia Tax Setup'),
				description: __('Configure your Company NPWP and NITKU for local compliance.'),
				fields: [
					{
						label: __('Company'),
						fieldname: 'company',
						fieldtype: 'Link',
						options: 'Company',
						reqd: 1,
						default: frappe.defaults.get_user_default('company')
					},
					{
						label: __('NPWP (15 digits)'),
						fieldname: 'npwp',
						fieldtype: 'Data',
						description: __('Format: 00.000.000.0-000.000')
					},
					{
						label: __('NITKU'),
						fieldname: 'nitku',
						fieldtype: 'Data',
						description: __('Branch identifier (3 digits)')
					}
				],
				action: (values) => this.save_tax_settings(values)
			},
			{
				title: __('Payment Gateway'),
				description: __('Connect your Midtrans or Xendit account.'),
				fields: [
					{
						label: __('Preferred Gateway'),
						fieldname: 'gateway',
						fieldtype: 'Select',
						options: ['Midtrans', 'Xendit'],
						reqd: 1
					},
					{
						label: __('Server Key / Secret'),
						fieldname: 'api_secret',
						fieldtype: 'Password',
						reqd: 1
					},
					{
						label: __('Client Key / ID'),
						fieldname: 'api_key',
						fieldtype: 'Data'
					}
				],
				action: (values) => this.save_payment_settings(values)
			},
			{
				title: __('WhatsApp API'),
				description: __('Connect to Meta Business API.'),
				fields: [
					{
						label: __('Account Name'),
						fieldname: 'account_name',
						fieldtype: 'Data',
						reqd: 1,
						default: 'Indo Connect'
					},
					{
						label: __('Phone Number ID'),
						fieldname: 'phone_number_id',
						fieldtype: 'Data',
						reqd: 1
					},
					{
						label: __('Access Token'),
						fieldname: 'access_token',
						fieldtype: 'Password',
						reqd: 1
					},
					{
						fieldtype: 'Button',
						label: __('Test Connection'),
						click: () => this.test_whatsapp_connection()
					}
				],
				action: (values) => this.save_whatsapp_account(values)
			}
		];
		this.show_step(0);
	}

	render_container() {
		this.container = $(`<div class="setup-wizard-container" style="max-width: 600px; margin: 50px auto; padding: 30px; border: 1px solid #d1d8dd; border-radius: 8px; background: #fff;">
			<div class="progress-container" style="margin-bottom: 30px;">
				<div class="progress" style="height: 8px;">
					<div class="progress-bar" style="width: 0%; background-color: var(--primary-color);"></div>
				</div>
			</div>
			<div class="step-content"></div>
			<div class="step-actions" style="margin-top: 30px; display: flex; justify-content: space-between;">
				<button class="btn btn-default btn-prev" style="display:none;">${__('Back')}</button>
				<button class="btn btn-primary btn-next">${__('Next')}</button>
			</div>
		</div>`).appendTo(this.page.main);

		this.container.find('.btn-next').click(() => this.next_step());
		this.container.find('.btn-prev').click(() => this.prev_step());
	}

	show_step(index) {
		this.current_step = index;
		const step = this.steps[index];
		const $content = this.container.find('.step-content').empty();

		$content.append(`<h3 style="margin-top:0;">${step.title}</h3>`);
		$content.append(`<p class="text-muted" style="margin-bottom: 20px;">${step.description}</p>`);

		this.field_group = new frappe.ui.FieldGroup({
			fields: step.fields,
			parent: $content
		});
		this.field_group.make();

		// Update Progress
		const progress = ((index + 1) / this.steps.length) * 100;
		this.container.find('.progress-bar').css('width', progress + '%');

		// Update Buttons
		this.container.find('.btn-prev').toggle(index > 0);
		this.container.find('.btn-next').text(index === this.steps.length - 1 ? __('Complete Setup') : __('Next'));
	}

	next_step() {
		const values = this.field_group.get_values();
		if (!values) return;

		const step = this.steps[this.current_step];
		frappe.dom.freeze(__('Processing...'));
		
		step.action(values).then(() => {
			frappe.dom.unfreeze();
			if (this.current_step < this.steps.length - 1) {
				this.show_step(this.current_step + 1);
			} else {
				this.finish();
			}
		}).catch((err) => {
			frappe.dom.unfreeze();
			frappe.msgprint(__('Error saving step: ') + err.message);
		});
	}

	prev_step() {
		this.show_step(this.current_step - 1);
	}

	save_tax_settings(values) {
		return frappe.call({
			method: 'frappe.client.set_value',
			args: {
				doctype: 'Company',
				name: values.company,
				fieldname: {
					'tax_id': values.npwp,
					'custom_companys_nitku': values.nitku
				}
			}
		});
	}

	save_payment_settings(values) {
		const doctype = values.gateway === 'Midtrans' ? 'Midtrans Settings' : 'Xendit Settings';
		return frappe.call({
			method: 'frappe.client.set_value',
			args: {
				doctype: doctype,
				name: doctype,
				fieldname: {
					'api_key': values.api_key,
					'api_secret': values.api_secret,
					'is_sandbox': 1
				}
			}
		});
	}

	save_whatsapp_account(values) {
		return frappe.call({
			method: 'frappe.client.insert',
			args: {
				doc: {
					doctype: 'WhatsApp Account',
					account_name: values.account_name,
					phone_number_id: values.phone_number_id,
					access_token: values.access_token
				}
			}
		});
	}

	test_whatsapp_connection() {
		const values = this.field_group.get_values();
		if (!values.phone_number_id || !values.access_token) {
			frappe.msgprint(__('Please enter Phone Number ID and Access Token first.'));
			return;
		}

		frappe.dom.freeze(__('Testing...'));
		frappe.call({
			method: 'frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_account.whatsapp_account.test_connection',
			args: {
				phone_number_id: values.phone_number_id,
				access_token: values.access_token
			},
			callback: (r) => {
				frappe.dom.unfreeze();
				if (r.message && r.message.status === 'success') {
					frappe.show_alert({
						message: __('Connection Successful!'),
						indicator: 'green'
					});
				} else {
					frappe.msgprint(__('Connection Failed: ') + (r.message ? r.message.error : __('Unknown Error')));
				}
			}
		});
	}

	finish() {
		frappe.call({
			method: 'frappe.client.set_value',
			args: {
				doctype: 'Onboarding Settings',
				name: 'Onboarding Settings',
				fieldname: 'setup_completed',
				value: 1
			}
		}).then(() => {
			frappe.msgprint({
				title: __('Success'),
				indicator: 'green',
				message: __('All systems are now configured! Redirecting to Workspace...')
			});
			setTimeout(() => {
				frappe.set_route('Workspaces', 'WhatsApp Integration');
			}, 2000);
		});
	}
}
