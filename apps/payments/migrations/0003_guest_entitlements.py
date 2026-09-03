from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('payments', '0002_native_store_payments')]
    operations = [
        migrations.CreateModel(
            name='GuestEntitlement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_digest', models.CharField(max_length=64, unique=True)),
                ('token_expires_at', models.DateTimeField(db_index=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('backing_user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='guest_subscription', to=settings.AUTH_USER_MODEL)),
                ('linked_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='linked_guest_subscriptions', to=settings.AUTH_USER_MODEL)),
                ('purchase', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='guest_entitlement', to='payments.storepurchase')),
            ], options={'db_table': 'GuestEntitlement'},
        ),
        migrations.AddConstraint(model_name='storepurchase', constraint=models.UniqueConstraint(condition=~models.Q(original_transaction_id=''), fields=('platform', 'original_transaction_id'), name='uniq_store_original_transaction')),
        migrations.AddConstraint(model_name='storepurchase', constraint=models.UniqueConstraint(condition=~models.Q(latest_transaction_id=''), fields=('platform', 'latest_transaction_id'), name='uniq_store_latest_transaction')),
    ]
